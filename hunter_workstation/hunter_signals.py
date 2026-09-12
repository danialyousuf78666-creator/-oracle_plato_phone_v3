from __future__ import annotations
import math, subprocess, tempfile, wave
from pathlib import Path
from typing import Any
import numpy as np
from hunter_common import clip

def _validated_frequency(values, fps: float, min_cycles: float = 2.5, max_hz: float = 10.0) -> dict[str, Any]:
    """Conservative low-frequency estimator with detrending and split-window stability."""
    arr = np.asarray(values, dtype=float)
    out = {"frequency_hz": None,"validated": False,"strength": 0.0,"stability": 0.0,"cycles": 0.0,"reason": None}
    if fps <= 0 or arr.size < 16 or not np.all(np.isfinite(arr)):
        out["reason"] = "insufficient_samples_or_invalid_fps"; return out
    duration = arr.size / float(fps)
    t = np.linspace(-1.0, 1.0, arr.size)
    coef = np.polyfit(t, arr, 1); y = arr - np.polyval(coef, t)
    if float(np.std(y)) < 1e-9:
        out["reason"] = "no_measurable_detrended_signal"; return out
    def peak(z):
        z=np.asarray(z,dtype=float)
        if z.size<8: return None,0.0
        z=z-np.mean(z); win=np.hanning(z.size); spec=np.abs(np.fft.rfft(z*win))**2
        freq=np.fft.rfftfreq(z.size,d=1.0/float(fps)); valid=(freq>0)&(freq<=min(max_hz,fps/2.0))
        if not np.any(valid): return None,0.0
        fv,sv=freq[valid],spec[valid]; i=int(np.argmax(sv)); strength=float(sv[i]/(np.median(sv)+1e-12))
        return float(fv[i]),strength
    f,strength=peak(y)
    if f is None: out["reason"]="no_peak"; return out
    cycles=f*duration; out["cycles"]=float(cycles); out["strength"]=float(strength)
    if cycles<min_cycles: out["reason"]="too_few_cycles"; return out
    if strength<5.0: out["reason"]="weak_spectral_prominence"; return out
    n=arr.size; half=max(8,int(n*0.65)); f1,_=peak(y[:half]); f2,_=peak(y[-half:])
    if f1 is None or f2 is None: out["reason"]="subwindow_peak_missing"; return out
    tol=max(0.18,0.20*f); stable=abs(f1-f)<=tol and abs(f2-f)<=tol
    out["stability"]=float((int(abs(f1-f)<=tol)+int(abs(f2-f)<=tol))/2.0)
    if not stable: out["reason"]="subwindow_instability"; return out
    out["frequency_hz"]=float(f); out["validated"]=True; out["reason"]=None; return out


def _extract_audio_envelope(video_path: str | Path, cutoff_seconds: float | None = None, envelope_hz: int = 100) -> dict[str, Any]:
    result={"available":False,"sample_rate":None,"envelope_hz":envelope_hz,"envelope":[],"reason":None}; tmp=None
    try:
        tmpf=tempfile.NamedTemporaryFile(suffix=".wav",delete=False); tmp=Path(tmpf.name); tmpf.close()
        cmd=["ffmpeg","-y","-loglevel","error","-i",str(video_path)]
        if cutoff_seconds is not None and float(cutoff_seconds)>0: cmd += ["-t",f"{float(cutoff_seconds):.6f}"]
        cmd += ["-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",str(tmp)]
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
        if p.returncode!=0 or not tmp.exists() or tmp.stat().st_size<64:
            result["reason"]="ffmpeg_audio_extract_failed_or_no_audio"; return result
        with wave.open(str(tmp),"rb") as wf:
            sr=int(wf.getframerate()); raw=wf.readframes(wf.getnframes())
        x=np.frombuffer(raw,dtype=np.int16).astype(np.float32)/32768.0
        if x.size<max(32,sr//4): result["reason"]="audio_too_short"; return result
        hop=max(1,int(round(sr/envelope_hz))); n=x.size//hop
        if n<=2: result["reason"]="audio_envelope_too_short"; return result
        x=x[:n*hop].reshape(n,hop); env=np.sqrt(np.mean(x*x,axis=1)+1e-12)
        result.update({"available":True,"sample_rate":sr,"envelope_hz":float(sr/hop),"envelope":env.tolist(),"reason":None}); return result
    except FileNotFoundError:
        result["reason"]="ffmpeg_not_installed"; return result
    except Exception as ex:
        result["reason"]=f"audio_error:{type(ex).__name__}"; return result
    finally:
        if tmp is not None:
            try: tmp.unlink(missing_ok=True)
            except Exception: pass


def _resample_signal(values, source_hz: float, target_hz: float, n_target: int | None = None) -> np.ndarray:
    x=np.asarray(values,dtype=float)
    if x.size==0 or source_hz<=0 or target_hz<=0: return np.array([],dtype=float)
    duration=(x.size-1)/source_hz if x.size>1 else 0.0
    if duration<=0: return x.copy()
    if n_target is None: n_target=max(2,int(round(duration*target_hz))+1)
    t0=np.arange(x.size)/source_hz; t1=np.linspace(0.0,duration,n_target); return np.interp(t1,t0,x)


def _lagged_correlation(a,b,hz:float,max_lag_s:float=0.5)->dict[str,Any]:
    a=np.asarray(a,dtype=float); b=np.asarray(b,dtype=float); n=min(a.size,b.size)
    if n<16 or hz<=0: return {"correlation":0.0,"lag_s":None}
    a,b=a[:n],b[:n]; a=(a-np.mean(a))/(np.std(a)+1e-12); b=(b-np.mean(b))/(np.std(b)+1e-12)
    maxlag=min(n//3,int(round(max_lag_s*hz))); best=(0.0,0)
    for lag in range(-maxlag,maxlag+1):
        if lag<0: aa,bb=a[-lag:],b[:n+lag]
        elif lag>0: aa,bb=a[:n-lag],b[lag:]
        else: aa,bb=a,b
        if aa.size<8: continue
        c=float(np.mean(aa*bb))
        if abs(c)>abs(best[0]): best=(c,lag)
    return {"correlation":float(best[0]),"lag_s":float(best[1]/hz)}


def _global_signal_context(brightness_series,motion_series,fps:float,video_path:str|Path,cutoff_seconds:float|None,row_artifact_series=None)->dict[str,Any]:
    brightness=np.asarray(brightness_series,dtype=float); motion=np.asarray(motion_series,dtype=float)
    missing={"validated":False,"frequency_hz":None,"strength":0,"stability":0,"cycles":0,"reason":"missing"}
    brightness_freq=_validated_frequency(brightness,fps,min_cycles=2.5,max_hz=min(10.0,fps/2.0)) if brightness.size else dict(missing)
    motion_freq=_validated_frequency(motion,fps,min_cycles=2.5,max_hz=min(10.0,fps/2.0)) if motion.size else dict(missing)
    row_artifact=float(np.median(row_artifact_series)) if row_artifact_series else 0.0
    flicker_score=clip(math.log1p(float(brightness_freq.get("strength",0)))/math.log(100.0)) if brightness_freq.get("validated") else 0.0
    rolling_score=clip(row_artifact*2.0); optical_nuisance=clip(max(flicker_score,rolling_score))
    audio=_extract_audio_envelope(video_path,cutoff_seconds)
    audio_freq={"validated":False,"frequency_hz":None,"strength":0,"stability":0,"cycles":0,"reason":audio.get("reason")}
    acoustic_activity=0.0; av={"correlation":0.0,"lag_s":None}
    if audio.get("available"):
        env=np.asarray(audio.get("envelope",[]),dtype=float); ehz=float(audio.get("envelope_hz") or 0)
        if env.size:
            med=float(np.median(env)); spread=float(np.percentile(env,95)-np.percentile(env,25)); acoustic_activity=clip(spread/(med+spread+1e-9))
            audio_freq=_validated_frequency(env,ehz,min_cycles=2.5,max_hz=min(10.0,ehz/2.0))
            target_hz=min(float(fps),float(ehz),50.0)
            if target_hz>0 and motion.size:
                dur=min((motion.size-1)/fps if motion.size>1 else 0,(env.size-1)/ehz if env.size>1 else 0)
                if dur>0:
                    n=max(16,int(dur*target_hz)); mr=_resample_signal(motion,fps,target_hz,n); ar=_resample_signal(env,ehz,target_hz,n); av=_lagged_correlation(mr,ar,target_hz,0.5)
    resonance=0.0; resonance_reason="insufficient_independent_frequency_evidence"
    if motion_freq.get("validated") and audio_freq.get("validated"):
        fm=float(motion_freq["frequency_hz"]); fa=float(audio_freq["frequency_hz"]); tol=max(0.18,0.15*max(fm,fa))
        if abs(fm-fa)<=tol and optical_nuisance<0.75:
            closeness=1.0-clip(abs(fm-fa)/(tol+1e-12)); resonance=clip(closeness*min(float(motion_freq.get("stability",0)),float(audio_freq.get("stability",0)))*(1.0-optical_nuisance)); resonance_reason="independent_motion_audio_envelope_frequency_agreement"
        elif optical_nuisance>=0.75: resonance_reason="blocked_by_optical_nuisance"
        else: resonance_reason="motion_audio_frequency_disagreement"
    return {"brightness_frequency":brightness_freq,"motion_frequency":motion_freq,"audio_envelope_frequency":audio_freq,"optical_nuisance_score":optical_nuisance,"flicker_score":flicker_score,"rolling_shutter_proxy_score":rolling_score,"acoustic_activity_score":acoustic_activity,"audio_visual":av,"resonance_candidate_score":resonance,"resonance_reason":resonance_reason,"audio_available":bool(audio.get("available")),"audio_reason":audio.get("reason"),"claim_boundary":"Signal scores are screening evidence, not calibrated probabilities or proof of resonance/causation."}
