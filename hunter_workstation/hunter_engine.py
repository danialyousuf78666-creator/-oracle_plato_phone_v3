from __future__ import annotations
import hashlib, json, math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.special import ndtr

SPECIALISTS=["M1_VISUAL","M2_MOTION","M3_FREQUENCY","M4_OPTICAL","M5_GEOMETRY","M6_ACOUSTIC","M7_RESONANCE","M8_ANOMALY","M9_PROPAGATION","M10_RELATIONSHIP","M11_CHALLENGER"]
EXTRACTED="E"

def clip(x):
    try:return max(0.0,min(1.0,float(x)))
    except:return 0.0

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def lock_report(report_path):
    p=Path(report_path); out=p.with_suffix(p.suffix+".lock.json")
    payload={"report":str(p),"sha256":sha256_file(p),"locked_at_utc":datetime.now(timezone.utc).isoformat(),"post_draw_adjustment":False,"random_ticket_fallback":False}
    out.write_text(json.dumps(payload,indent=2),encoding="utf-8"); return out

@dataclass(frozen=True)
class Detection:
    frame:int; x:float; y:float; r:float; score:float=1.0
@dataclass
class TrackPoint:
    frame:int; x:float; y:float; r:float; score:float=1.0
@dataclass
class Track:
    track_id:int; points:list[TrackPoint]=field(default_factory=list); missed:int=0; active:bool=True
    @property
    def last(self): return self.points[-1]

class HoughBallDetector:
    def __init__(self,min_radius=5,max_radius=80,min_dist=12,param1=120,param2=22):
        self.min_radius=int(min_radius); self.max_radius=int(max_radius); self.min_dist=float(min_dist); self.param1=float(param1); self.param2=float(param2)
    def detect(self,frame,frame_index):
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY); gray=cv2.GaussianBlur(gray,(5,5),1.2)
        circles=cv2.HoughCircles(gray,cv2.HOUGH_GRADIENT,dp=1.2,minDist=self.min_dist,param1=self.param1,param2=self.param2,minRadius=self.min_radius,maxRadius=self.max_radius)
        if circles is None:return []
        return [Detection(frame_index,float(x),float(y),float(r),1.0) for x,y,r in circles[0]]

class HungarianTracker:
    def __init__(self,max_distance=55,max_missed=3):
        self.max_distance=float(max_distance); self.max_missed=int(max_missed); self.tracks=[]; self._next_id=1
    def _new(self,d):
        self.tracks.append(Track(self._next_id,[TrackPoint(d.frame,d.x,d.y,d.r,d.score)])); self._next_id+=1
    def update(self,detections):
        active=[t for t in self.tracks if t.active]
        if not active:
            for d in detections:self._new(d)
            return
        if not detections:
            for t in active:
                t.missed+=1
                if t.missed>self.max_missed:t.active=False
            return
        cost=np.array([[math.hypot(t.last.x-d.x,t.last.y-d.y) for d in detections] for t in active],dtype=float)
        rows,cols=linear_sum_assignment(cost); mt=set(); md=set()
        for i,j in zip(rows,cols):
            if cost[i,j]>self.max_distance:continue
            t,d=active[i],detections[j]; t.points.append(TrackPoint(d.frame,d.x,d.y,d.r,d.score)); t.missed=0; mt.add(t.track_id); md.add(j)
        for t in active:
            if t.track_id not in mt:
                t.missed+=1
                if t.missed>self.max_missed:t.active=False
        for j,d in enumerate(detections):
            if j not in md:self._new(d)

def track_features(track,fps,frame_w,frame_h,zone):
    pts=sorted(track.points,key=lambda p:p.frame)
    if len(pts)<3:return {"quality":0,"zone":0,"proximity":0,"approach":0,"speed":0,"circulation":0,"acceleration":0,"dwell":0}
    frames=np.array([p.frame for p in pts],float); xy=np.array([[p.x,p.y] for p in pts],float); t=frames/fps
    x0,y0,x1,y1=zone; ex,ey=(x0+x1)/2,(y0+y1)/2
    vx=np.gradient(xy[:,0],t); vy=np.gradient(xy[:,1],t); ax=np.gradient(vx,t); ay=np.gradient(vy,t); speed=np.hypot(vx,vy); acc=np.hypot(ax,ay)
    d=np.hypot(xy[:,0]-ex,xy[:,1]-ey); diag=max(math.hypot(frame_w,frame_h),1.0); proximity=1-float(np.clip(np.mean(d)/diag,0,1))
    inside=(xy[:,0]>=x0)&(xy[:,0]<=x1)&(xy[:,1]>=y0)&(xy[:,1]<=y1); zone_score=float(np.mean(inside)); dwell=clip(np.sum(inside)/(fps*2.0))
    vec=np.column_stack([ex-xy[:,0],ey-xy[:,1]]); norm=np.linalg.norm(vec,axis=1); norm[norm==0]=1; unit=vec/norm[:,None]
    approach_raw=vx*unit[:,0]+vy*unit[:,1]; approach=clip(np.mean(np.maximum(approach_raw,0))/(np.percentile(speed,90)+1e-6))
    speed_score=clip(np.mean(speed)/(diag*fps*0.15+1e-6)); acc_score=clip(np.mean(acc)/(diag*fps*fps*0.08+1e-6))
    angles=np.unwrap(np.arctan2(xy[:,1]-frame_h/2,xy[:,0]-frame_w/2)); circulation=clip(np.std(np.diff(angles))*3) if len(angles)>2 else 0
    quality=clip(len(pts)/(fps*2.0))
    return {"quality":quality,"zone":zone_score,"proximity":proximity,"approach":approach,"speed":speed_score,"circulation":circulation,"acceleration":acc_score,"dwell":dwell}

@dataclass
class MarkovModel:
    states:list[str]; transition:np.ndarray
    @classmethod
    def neutral(cls):return cls([EXTRACTED],np.array([[1.0]],float))
    @classmethod
    def load(cls,path):
        d=json.loads(Path(path).read_text()); return cls(list(d["states"]),np.asarray(d["transition"],float))
    def absorption_probability(self,start,horizon=30):
        if start is None or start not in self.states:return 0.0
        idx={s:i for i,s in enumerate(self.states)}; v=np.zeros(len(self.states)); v[idx[start]]=1
        for _ in range(max(0,int(horizon))):v=v@self.transition
        return float(v[idx[EXTRACTED]])

def discretize_state(x,y,vx,vy,w,h,grid=3):
    gx=min(grid-1,max(0,int((x/max(w,1e-9))*grid))); gy=min(grid-1,max(0,int((y/max(h,1e-9))*grid)))
    d=("R" if vx>=0 else "L") if abs(vx)>=abs(vy) else ("D" if vy>=0 else "U"); return f"{gx}:{gy}:{d}"

def track_state(track,fps,w,h):
    pts=sorted(track.points,key=lambda p:p.frame)
    if len(pts)<2:return None
    a,b=pts[-2],pts[-1]; dt=max((b.frame-a.frame)/fps,1e-9); return discretize_state(b.x,b.y,(b.x-a.x)/dt,(b.y-a.y)/dt,w,h)

def radiation_score(track,fps,zone,horizon=1.0,steps=20,diffusion=30.0):
    pts=sorted(track.points,key=lambda p:p.frame)
    if len(pts)<3:return {"score":0.0,"peak_zone_probability":0.0,"time_to_peak_s":None}
    pts=pts[-8:]; t=np.array([p.frame for p in pts],float)/fps; x=np.array([p.x for p in pts],float); y=np.array([p.y for p in pts],float); tau=t-t[-1]
    A=np.column_stack([np.ones_like(tau),tau]); bx,*_=np.linalg.lstsq(A,x,rcond=None); by,*_=np.linalg.lstsq(A,y,rcond=None)
    residual=np.concatenate([x-A@bx,y-A@by]); sigma0=float(np.sqrt(np.mean(residual*residual))) if residual.size else 0.0
    x0,y0,x1,y1=map(float,zone); ts=np.linspace(horizon/steps,horizon,steps); probs=[]; weights=[]
    for dt in ts:
        mx=bx[0]+bx[1]*dt; my=by[0]+by[1]*dt; sigma=math.sqrt(max(2.0,sigma0)**2+2*max(diffusion,0)*dt)
        px=float(ndtr((x1-mx)/sigma)-ndtr((x0-mx)/sigma)); py=float(ndtr((y1-my)/sigma)-ndtr((y0-my)/sigma)); p=clip(px*py); probs.append(p); weights.append(math.exp(-dt/0.7))
    arr=np.asarray(probs); w=np.asarray(weights); score=float(np.sum(arr*w)/max(np.sum(w),1e-12)); k=int(np.argmax(arr))
    return {"score":clip(score),"peak_zone_probability":float(arr[k]),"time_to_peak_s":float(ts[k]),"sigma0_px":sigma0}

def base_score(f,markov):
    weights={"zone":.24,"proximity":.20,"approach":.20,"markov":.18,"speed":.08,"circulation":.05,"quality":.05}; vals=dict(f); vals["markov"]=markov
    return float(sum(weights[k]*float(vals.get(k,0)) for k in weights))

class RecoveryState:
    def __init__(self,root):self.root=Path(root); self.files=self._load()
    def _load(self):
        out={}
        for name in ["shared_memory.json","deep_signatures.jsonl","screen_signatures.jsonl","V0_2_7_CANDIDATE_FREEZE.json"]:
            p=self.root/name
            if p.exists():
                meta={"path":str(p),"sha256":sha256_file(p),"bytes":p.stat().st_size}
                if p.suffix==".jsonl":
                    try:meta["records"]=sum(1 for line in p.open(errors="ignore") if line.strip())
                    except:pass
                out[name]=meta
        return out
    def audit(self):return {"recovery_root":str(self.root),"loaded_files":self.files,"legacy_state_present":any(k in self.files for k in ["shared_memory.json","deep_signatures.jsonl","screen_signatures.jsonl"])}

class HeadRouter:
    def __init__(self,recovery):self.recovery=recovery
    def evaluate(self,rec,peers):
        f=rec["features"]; q=clip(f.get("quality")); prox=clip(f.get("proximity")); app=clip(f.get("approach")); sp=clip(f.get("speed")); circ=clip(f.get("circulation")); zone=clip(f.get("zone")); mk=clip(rec.get("markov")); rad=clip(rec.get("radiation",{}).get("score"))
        peer=[float(p.get("base_score",0)) for p in peers if p is not rec]; relation=clip(1-abs(float(rec.get("base_score",0))-sum(peer)/len(peer))) if peer else 0
        s={"M1_VISUAL":q,"M2_MOTION":clip(.6*app+.4*sp),"M3_FREQUENCY":circ,"M4_OPTICAL":clip(.7*q+.3*prox),"M5_GEOMETRY":clip(.55*prox+.45*zone),"M6_ACOUSTIC":0.0,"M7_RESONANCE":0.0,"M8_ANOMALY":clip(q*(1-abs(app-prox))),"M9_PROPAGATION":clip(.6*mk+.4*rad),"M10_RELATIONSHIP":relation,"M11_CHALLENGER":prox}
        w={"M1_VISUAL":.10,"M2_MOTION":.16,"M3_FREQUENCY":.06,"M4_OPTICAL":.08,"M5_GEOMETRY":.16,"M6_ACOUSTIC":0,"M7_RESONANCE":0,"M8_ANOMALY":.08,"M9_PROPAGATION":.18,"M10_RELATIONSHIP":.08,"M11_CHALLENGER":.10}; d=sum(w.values()) or 1
        return {"scores":s,"weights":w,"fusion":clip(sum(s[k]*w[k] for k in SPECIALISTS)/d),"mode":"legacy_state_plus_physical_proxy" if "shared_memory.json" in self.recovery.files else "physical_proxy_compatibility","random_completion":False}

def mask_frame(frame,chamber_roi=None,overlay_masks=None):
    h,w=frame.shape[:2]; out=np.zeros_like(frame)
    if chamber_roi is None:out[:]=frame
    else:
        x0,y0,x1,y1=[int(round(v)) for v in chamber_roi]; x0=max(0,min(w,x0));x1=max(0,min(w,x1));y0=max(0,min(h,y0));y1=max(0,min(h,y1))
        if x1>x0 and y1>y0:out[y0:y1,x0:x1]=frame[y0:y1,x0:x1]
    for r in overlay_masks or []:
        x0,y0,x1,y1=[int(round(v)) for v in r]; x0=max(0,min(w,x0));x1=max(0,min(w,x1));y0=max(0,min(h,y0));y1=max(0,min(h,y1)); out[y0:y1,x0:x1]=0
    return out

def analyze_video(video_path,extraction_zone,identity_map=None,markov_model=None,chamber_roi=None,overlay_masks=None,cutoff_seconds=None,radiation_weight=.10,specialist_weight=.20,recovery_dir="recovery"):
    cap=cv2.VideoCapture(str(video_path))
    if not cap.isOpened():raise RuntimeError(f"cannot open video: {video_path}")
    fps=float(cap.get(cv2.CAP_PROP_FPS)); w=float(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h=float(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not math.isfinite(fps) or fps<=0:raise RuntimeError("invalid FPS")
    tracker=HungarianTracker(); detector=HoughBallDetector(); fi=0; cutoff_frames=None if cutoff_seconds is None else max(1,int(float(cutoff_seconds)*fps))
    while True:
        ok,frame=cap.read()
        if not ok or (cutoff_frames is not None and fi>=cutoff_frames):break
        tracker.update(detector.detect(mask_frame(frame,chamber_roi,overlay_masks),fi));fi+=1
    cap.release(); markov=markov_model or MarkovModel.neutral(); rw=max(0,min(.25,float(radiation_weight))); sw=max(0,min(.40,float(specialist_weight))); recovery=RecoveryState(recovery_dir); head=HeadRouter(recovery)
    ranked=[]; number_scores={}; direct={int(k):int(v) for k,v in (identity_map or {}).items()}
    for t in tracker.tracks:
        f=track_features(t,fps,w,h,extraction_zone); st=track_state(t,fps,w,h); mk=markov.absorption_probability(st,30); bs=base_score(f,mk); rad=radiation_score(t,fps,extraction_zone)
        ranked.append({"track_id":t.track_id,"number":direct.get(t.track_id),"base_score":bs,"markov":mk,"radiation":rad,"state":st,"features":f,"n_points":len(t.points)})
    for rec in ranked:
        spec=head.evaluate(rec,ranked); rec["specialists"]=spec; f=rec["features"]
        b1=float(f.get("proximity",0)); b2=float(.6*f.get("approach",0)+.4*f.get("speed",0)); b3=float(.24*f.get("zone",0)+.20*f.get("proximity",0)+.20*f.get("approach",0)+.08*f.get("speed",0)+.05*f.get("circulation",0)+.05*f.get("quality",0)); b4=float(rec["base_score"]); b5=(1-rw)*b4+rw*float(rec["radiation"]["score"]); b6=float(spec["fusion"]); final=(1-sw)*b5+sw*b6
        rec["score"]=float(final); rec["baselines"]={"B1_distance":b1,"B2_motion":b2,"B3_physical":b3,"B4_physical_markov":b4,"B5_plus_radiation":b5,"B6_specialists":b6,"B7_full_hybrid":float(final)}
        if rec["number"] is not None and 1<=int(rec["number"])<=45:number_scores[int(rec["number"])]=max(number_scores.get(int(rec["number"]),-1),float(final))
    ranked.sort(key=lambda r:(-r["score"],r["track_id"])); valid=sorted(number_scores.items(),key=lambda x:(-x[1],x[0])); top6=sorted(n for n,_ in valid[:6]) if len(valid)>=6 else []
    return {"game":"Saturday Lotto","version":"hunter-workstation-0.3.0","scientific_status":"experimental_no_predictive_edge_claim","random_ticket_fallback":False,"post_draw_adjustment":False,"broadcast_protection":{"chamber_roi":chamber_roi,"overlay_masks":overlay_masks or [],"cutoff_seconds":cutoff_seconds},"frames_processed":fi,"fps":fps,"markov_trained":len(markov.states)>1,"radiation_weight":rw,"specialist_weight":sw,"identity_mode":"direct_map" if direct else "anonymous","anonymous_track_ranking":ranked,"top6_status":"locked_candidate" if len(top6)==6 else "insufficient_numbered_tracks","top6":top6,"audit":recovery.audit()}

def save_report(report,path):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(report,indent=2),encoding="utf-8")
