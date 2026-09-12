from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np

SPECIALISTS = (
    ("M1_FREQUENCY", "Frequency balance"),
    ("M2_GAPS", "Gap / recency structure"),
    ("M3_SERIAL", "Serial overlap"),
    ("M4_MARKOV", "Markov dependence"),
    ("M5_PAIRS", "Pair recurrence"),
    ("M6_GEOMETRY", "Draw geometry"),
    ("M7_ENTROPY", "Entropy / complexity"),
    ("M8_REGIME", "Regime change"),
    ("M9_PERIODICITY", "Periodicity"),
    ("M10_STABILITY", "Cross-window stability"),
    ("M11_CHALLENGER", "Challenger"),
)

@dataclass(frozen=True)
class HunterRandomnessConfig:
    pool_size: int = 45
    draw_size: int = 6
    monte_carlo_trials: int = 240
    calibration_seed: int = 918273
    windows: tuple[int, ...] = (100, 150, 250)
    fdr_alpha: float = 0.10
    min_draws: int = 60

def validate_draws(draws, config: HunterRandomnessConfig):
    arr=np.asarray(draws,dtype=np.int16)
    if arr.ndim!=2: raise ValueError("draws must be a 2D array")
    if arr.shape[0] < config.min_draws: raise ValueError(f"at least {config.min_draws} draws are required")
    if arr.shape[1] != config.draw_size: raise ValueError(f"each draw must contain exactly {config.draw_size} values")
    if np.any(arr<1) or np.any(arr>config.pool_size): raise ValueError("draw contains value outside pool")
    for row in arr:
        if len(set(map(int,row))) != len(row): raise ValueError("duplicate value inside a draw")
    return np.sort(arr,axis=1)

def generate_uniform_draws(n_draws=600, *, config=None, seed=1):
    c=config or HunterRandomnessConfig()
    rng=np.random.default_rng(seed)
    scores=rng.random((n_draws,c.pool_size))
    d=np.argpartition(scores,c.draw_size-1,axis=1)[:,:c.draw_size]+1
    d.sort(axis=1)
    return d.astype(np.int16)

def generate_alternative(n_draws=600, *, config=None, seed=2, kind="frequency_bias", strength=0.25):
    c=config or HunterRandomnessConfig()
    rng=np.random.default_rng(seed)
    pop=np.arange(1,c.pool_size+1)
    out=np.empty((n_draws,c.draw_size),dtype=np.int16)
    prev=None
    for t in range(n_draws):
        w=np.ones(c.pool_size,dtype=float)
        forced=[]
        if kind=="frequency_bias":
            w[6] *= 1 + 6*strength
        elif kind=="serial_persistence" and prev is not None and rng.random() < strength:
            forced=[int(rng.choice(prev))]
        elif kind=="regime_shift" and t >= n_draws//2:
            w[:max(3,c.pool_size//5)] *= 1 + 4*strength
        elif kind=="periodicity":
            residue = t % 5
            w[np.arange(c.pool_size) % 5 == residue] *= 1 + 7*strength
        allowed=pop[~np.isin(pop,forced)]
        p=w[allowed-1]; p=p/p.sum()
        rest=rng.choice(allowed,c.draw_size-len(forced),replace=False,p=p)
        row=np.sort(np.asarray(forced+rest.tolist(),dtype=np.int16))
        out[t]=row; prev=row
    return out

def _indicators(draws,pool):
    x=np.zeros((len(draws),pool),dtype=np.float64)
    x[np.arange(len(draws))[:,None],draws-1]=1
    return x

def _js(p,q):
    p=np.asarray(p,float); q=np.asarray(q,float)
    p=p/p.sum(); q=q/q.sum()
    m=.5*(p+q)
    def kl(a,b):
        mask=a>0
        return float(np.sum(a[mask]*np.log((a[mask]+1e-12)/(b[mask]+1e-12))))
    return .5*kl(p,m)+.5*kl(q,m)

def _gap_dispersion(draws,pool):
    vals=[]
    for n in range(1,pool+1):
        idx=np.flatnonzero(np.any(draws==n,axis=1))
        if len(idx)>=5:
            g=np.diff(idx).astype(float)
            if g.mean()>0:
                vals.append(float(g.std(ddof=1)/(g.mean()+1e-9)))
    return float(np.mean(vals)) if vals else 0.0

def _pair_collision(draws,pool):
    _,k=draws.shape
    ids=[]
    for i in range(k):
        for j in range(i+1,k):
            ids.append((draws[:,i]-1)*pool+(draws[:,j]-1))
    counts=np.bincount(np.concatenate(ids),minlength=pool*pool)
    return float(np.sum(counts*(counts-1)/2))

def _serial_metrics(x):
    if len(x)<3: return 0.0,0.0
    a=x[:-1]-x[:-1].mean(axis=0)
    b=x[1:]-x[1:].mean(axis=0)
    den=np.sqrt((a*a).sum(0)*(b*b).sum(0))
    corr=np.divide((a*b).sum(0),den,out=np.zeros(x.shape[1]),where=den>1e-12)
    return float(np.max(np.abs(corr))), float(np.mean(np.abs(corr)))

def _periodicity(draws):
    pool=int(np.max(draws))
    x=_indicators(draws,pool)
    x=x-x.mean(axis=0,keepdims=True)
    if len(x)<12:
        return 0.0
    power=np.abs(np.fft.rfft(x,axis=0))**2
    if power.shape[0] <= 2:
        return 0.0
    power=power[1:]
    mean_power=power.mean(axis=0)+1e-12
    ratios=power.max(axis=0)/mean_power
    return float(np.max(ratios))

def _geometry(draws):
    sums=draws.sum(axis=1).astype(float)
    ranges=(draws[:,-1]-draws[:,0]).astype(float)
    adj=(np.diff(draws,axis=1)==1).sum(axis=1).astype(float)
    return float(np.std(sums)/(np.mean(sums)+1e-9) + np.std(ranges)/(np.mean(ranges)+1e-9) + np.mean(adj)/draws.shape[1])

def _entropy_deficiency(draws,pool):
    counts=np.bincount(draws.ravel(),minlength=pool+1)[1:].astype(float)
    p=counts/counts.sum()
    h=-np.sum(p[p>0]*np.log2(p[p>0]))
    return float(1-h/math.log2(pool))

def _overlap(draws):
    a=draws[:-1,None,:]; b=draws[1:,:,None]
    return float(np.equal(a,b).any(axis=2).sum(axis=1).mean())

def _frequency_chi2(draws,pool):
    counts=np.bincount(draws.ravel(),minlength=pool+1)[1:].astype(float)
    exp=counts.sum()/pool
    return float(np.sum((counts-exp)**2/(exp+1e-12)))

def _window_drift(draws,pool,window=100):
    if len(draws)<2*window:
        window=max(20,len(draws)//3)
    if len(draws)<2*window: return 0.0
    recent=np.bincount(draws[-window:].ravel(),minlength=pool+1)[1:].astype(float)+.5
    prior=np.bincount(draws[-2*window:-window].ravel(),minlength=pool+1)[1:].astype(float)+.5
    return _js(recent,prior)

def raw_specialist_metrics(draws,pool):
    x=_indicators(draws,pool)
    maxcorr,meancorr=_serial_metrics(x)
    mid=max(1,len(draws)//2)
    c1=np.bincount(draws[:mid].ravel(),minlength=pool+1)[1:].astype(float)+.5
    c2=np.bincount(draws[mid:].ravel(),minlength=pool+1)[1:].astype(float)+.5
    return {
        "M1_FREQUENCY": _frequency_chi2(draws,pool),
        "M2_GAPS": _gap_dispersion(draws,pool),
        "M3_SERIAL": _overlap(draws),
        "M4_MARKOV": maxcorr+meancorr,
        "M5_PAIRS": _pair_collision(draws,pool),
        "M6_GEOMETRY": _geometry(draws),
        "M7_ENTROPY": _entropy_deficiency(draws,pool),
        "M8_REGIME": _js(c1,c2),
        "M9_PERIODICITY": _periodicity(draws),
        "M10_STABILITY": _window_drift(draws,pool,window=min(100,max(20,len(draws)//4))),
    }

def _bh(pvals):
    names=list(pvals)
    p=np.array([pvals[n] for n in names],float)
    order=np.argsort(p); ranked=p[order]; m=len(p)
    q=np.empty(m,float); prev=1.0
    for j in range(m-1,-1,-1):
        rank=j+1
        prev=min(prev, ranked[j]*m/rank)
        q[order[j]]=prev
    return {n:float(min(1,max(0,q[i]))) for i,n in enumerate(names)}

def _empirical_calibration(draws,c):
    observed=raw_specialist_metrics(draws,c.pool_size)
    names=list(observed)
    rng=np.random.default_rng(c.calibration_seed + len(draws)*17 + draws.shape[1])
    null=np.empty((c.monte_carlo_trials,len(names)),float)
    for i in range(c.monte_carlo_trials):
        scores=rng.random((len(draws),c.pool_size))
        d=np.argpartition(scores,c.draw_size-1,axis=1)[:,:c.draw_size]+1
        d.sort(axis=1)
        met=raw_specialist_metrics(d.astype(np.int16),c.pool_size)
        null[i]=[met[n] for n in names]
    obs=np.array([observed[n] for n in names],float)
    center=np.median(null,axis=0)
    mad=np.median(np.abs(null-center),axis=0)*1.4826
    sd=null.std(axis=0,ddof=1)
    scale=np.where(mad>1e-9,mad,np.where(sd>1e-9,sd,1.0))
    z=(obs-center)/scale
    p={n:float((1+np.count_nonzero(null[:,j] >= obs[j]))/(len(null)+1)) for j,n in enumerate(names)}
    null_z=(null-center)/scale
    max_null=np.max(null_z,axis=1)
    global_p=float((1+np.count_nonzero(max_null >= np.max(z)))/(len(null)+1))
    return observed,p,z,global_p,names,center,scale

def analyze_hunter_randomness(draws, config=None):
    c=config or HunterRandomnessConfig()
    arr=validate_draws(draws,c)
    raw,p,z,global_p,names,center,scale=_empirical_calibration(arr,c)
    q=_bh(p)
    window_rows=[]; support={n:0 for n in names}
    windows=[w for w in c.windows if len(arr)>=w]+[len(arr)]
    seen=[]
    for w in windows:
        if w in seen: continue
        seen.append(w)
        wm=raw_specialist_metrics(arr[-w:],c.pool_size)
        ratio=math.sqrt(w/len(arr)); row={"window":int(w)}
        for j,n in enumerate(names):
            wz=((wm[n]-center[j])/scale[j])*ratio
            row[n]=float(wz)
            if wz>=1.5: support[n]+=1
        window_rows.append(row)
    denom=max(1,len(window_rows))
    stability={n:support[n]/denom for n in names}
    persistent=[n for n in names if q[n] <= c.fdr_alpha and stability[n] >= 0.5]
    fragile=[n for n in names if q[n] <= c.fdr_alpha and stability[n] < 0.5]
    challenger_penalty=float(len(fragile)/(max(1,len(persistent)+len(fragile))))
    challenger_pass=(len(fragile)==0 or len(persistent)>=len(fragile)) and global_p<0.10
    if global_p >= 0.10 and not persistent:
        verdict="consistent_with_null"; label="Consistent with calibrated randomness"
    elif global_p < 0.01 and len(persistent)>=2 and challenger_penalty<=0.34:
        verdict="strong_persistent_departure"; label="Strong persistent departure from null"
    elif global_p < 0.05 and persistent:
        verdict="persistent_departure"; label="Persistent departure — investigate"
    elif global_p < 0.05 and not persistent:
        verdict="likely_unstable_or_nuisance"; label="Apparent structure failed stability challenge"
    else:
        verdict="inconclusive"; label="Weak / inconclusive structure"
    title_map=dict(SPECIALISTS); spec=[]
    for j,n in enumerate(names):
        status="persistent" if n in persistent else ("fragile" if n in fragile else "clear")
        spec.append({"id":n,"name":title_map[n],"raw":float(raw[n]),"z":float(z[j]),"p":float(p[n]),"q":float(q[n]),"window_support":float(stability[n]),"status":status})
    spec.append({"id":"M11_CHALLENGER","name":title_map["M11_CHALLENGER"],"raw":challenger_penalty,"z":0.0,"p":1.0-global_p,"q":1.0-global_p,"window_support":float(len(persistent)/max(1,len(persistent)+len(fragile))),"status":"pass" if challenger_pass else "challenge"})
    spec.sort(key=lambda r:int(r["id"].split("_")[0][1:]))
    return {"engine":"hunter-randomness-adjudicator-0.7","verdict":verdict,"label":label,"global_p":global_p,"persistent_signals":persistent,"fragile_signals":fragile,"challenger_penalty":challenger_penalty,"challenger_pass":bool(challenger_pass),"specialists":spec,"windows":window_rows,"n_draws":int(len(arr)),"pool_size":c.pool_size,"draw_size":c.draw_size,"monte_carlo_trials":c.monte_carlo_trials,"calibration_seed":c.calibration_seed,"claim_boundary":"A calibrated null-vs-structure adjudicator. It does not estimate future lottery numbers or establish exploitability."}

def parse_draw_text(text: str, config=None):
    c=config or HunterRandomnessConfig(); rows=[]
    for raw in (text or "").splitlines():
        line=raw.strip()
        if not line: continue
        for token in [",",";","|","\t"]: line=line.replace(token," ")
        vals=[int(x) for x in line.split()]
        if len(vals)!=c.draw_size: raise ValueError(f"each line must contain exactly {c.draw_size} numbers")
        rows.append(vals)
    if not rows: raise ValueError("no draws found")
    return validate_draws(np.asarray(rows,dtype=np.int16),c)

def validation_suite(config=None,n_draws=500,seed=20260913):
    c=config or HunterRandomnessConfig()
    scenarios=[
        ("Pure null","random",generate_uniform_draws(n_draws,config=c,seed=seed)),
        ("Frequency bias","structured",generate_alternative(n_draws,config=c,seed=seed+1,kind="frequency_bias",strength=.30)),
        ("Serial persistence","structured",generate_alternative(n_draws,config=c,seed=seed+2,kind="serial_persistence",strength=.28)),
        ("Regime shift","structured",generate_alternative(n_draws,config=c,seed=seed+3,kind="regime_shift",strength=.35)),
        ("Periodic modulation","structured",generate_alternative(n_draws,config=c,seed=seed+4,kind="periodicity",strength=.40)),
    ]
    out=[]
    for scenario,truth,data in scenarios:
        r=analyze_hunter_randomness(data,c)
        out.append({"scenario":scenario,"truth":truth,**r})
    return out
