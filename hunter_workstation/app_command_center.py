from __future__ import annotations
import json, time
from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import streamlit as st
from hunter_randomness_v2 import HunterRandomnessConfig, SPECIALISTS, analyze_hunter_randomness, generate_uniform_draws, generate_alternative, parse_draw_text, validation_suite
from hunter_engine import ENGINE_VERSION, analyze_video, save_report, lock_report

APP_VERSION="HUNTER COMMAND CENTER 0.7"
RUN_ROOT=Path("runs"); RUN_ROOT.mkdir(exist_ok=True)
UPLOAD_ROOT=RUN_ROOT/"uploads"; UPLOAD_ROOT.mkdir(parents=True,exist_ok=True)

st.set_page_config(page_title="Hunter Command Center",page_icon="◉",layout="wide",initial_sidebar_state="expanded")
st.markdown("""
<style>
:root{--bg:#05080d;--panel:#0a1018;--line:#1d2b3a;--txt:#eaf2f8;--muted:#7f94a7;--cyan:#62e6ff}
html,body,[data-testid="stAppViewContainer"]{background:var(--bg);color:var(--txt)}
[data-testid="stHeader"]{background:rgba(5,8,13,.82);backdrop-filter:blur(12px)}
.block-container{max-width:1500px;padding-top:1rem;padding-bottom:4rem}
[data-testid="stSidebar"]{background:#070c12;border-right:1px solid var(--line)}
.h-head{display:flex;align-items:flex-end;justify-content:space-between;gap:1rem;padding:1.05rem 1.2rem;border:1px solid var(--line);border-radius:18px;background:linear-gradient(145deg,#0b121c,#070b11);margin-bottom:1rem}
.h-brand{font-size:1.72rem;font-weight:800;letter-spacing:.08em}.h-kicker{font-size:.72rem;letter-spacing:.22em;color:var(--cyan);font-weight:800}.h-sub{color:var(--muted);font-size:.88rem;margin-top:.35rem}.h-chip{border:1px solid #244557;color:#aeeeff;background:#0b1a23;border-radius:999px;padding:.42rem .72rem;font-size:.72rem;font-weight:800;white-space:nowrap}
.h-verdict{border:1px solid var(--line);border-radius:18px;padding:1.15rem 1.2rem;background:linear-gradient(145deg,#0c141e,#081019);margin:.7rem 0 1rem}.h-verdict h2{margin:.15rem 0 .2rem;font-size:1.38rem}.h-label{font-size:.69rem;color:var(--muted);letter-spacing:.16em;text-transform:uppercase;font-weight:800}
.spec-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.6rem}.spec{border:1px solid var(--line);background:var(--panel);border-radius:14px;padding:.78rem .85rem}.spec .id{font-size:.68rem;color:var(--cyan);letter-spacing:.13em;font-weight:800}.spec .name{font-size:.88rem;font-weight:750;margin:.15rem 0 .45rem}.spec .row{display:flex;justify-content:space-between;color:var(--muted);font-size:.74rem}.spec.persistent,.spec.pass{border-color:#245b47;background:#0a1713}.spec.fragile,.spec.challenge{border-color:#5a4725;background:#171208}.h-card{border:1px solid var(--line);background:var(--panel);border-radius:16px;padding:.95rem 1rem}div[data-testid="stMetric"]{background:var(--panel);border:1px solid var(--line);padding:.65rem .8rem;border-radius:14px}.stButton button{border-radius:12px;min-height:46px;font-weight:800}
@media(max-width:760px){.block-container{padding-left:.55rem;padding-right:.55rem}.h-head{align-items:flex-start;flex-direction:column}.spec-grid{grid-template-columns:1fr}.h-brand{font-size:1.35rem}}
</style>
""",unsafe_allow_html=True)

st.markdown(f"""<div class="h-head"><div><div class="h-kicker">EVIDENCE / RANDOMNESS / PHYSICS</div><div class="h-brand">HUNTER COMMAND CENTER</div><div class="h-sub">{APP_VERSION} · null-vs-structure adjudication · deterministic audit</div></div><div class="h-chip">11 SPECIALISTS · CHALLENGER ACTIVE</div></div>""",unsafe_allow_html=True)


def specialist_grid(result):
    cards=[]
    for s in result["specialists"]:
        cards.append(f"""<div class="spec {s['status']}"><div class="id">{s['id']}</div><div class="name">{s['name']}</div><div class="row"><span>status</span><b>{s['status'].upper()}</b></div><div class="row"><span>evidence z</span><b>{s['z']:.2f}</b></div><div class="row"><span>FDR q</span><b>{s['q']:.4f}</b></div><div class="row"><span>window support</span><b>{s['window_support']*100:.0f}%</b></div></div>""")
    st.markdown('<div class="spec-grid">'+''.join(cards)+'</div>',unsafe_allow_html=True)


def verdict_panel(r):
    st.markdown(f"""<div class="h-verdict"><div class="h-label">Executive head verdict</div><h2>{r['label']}</h2><div style="color:#7f94a7;font-size:.88rem">Global family-wise null p = <b>{r['global_p']:.4f}</b> · persistent signals = <b>{len(r['persistent_signals'])}</b> · fragile signals = <b>{len(r['fragile_signals'])}</b> · challenger penalty = <b>{r['challenger_penalty']:.2f}</b></div></div>""",unsafe_allow_html=True)


def video_meta(path):
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened(): raise RuntimeError("Video could not be opened")
    fps=float(cap.get(cv2.CAP_PROP_FPS) or 0); w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0); h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0); frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0); cap.release()
    if fps<=0 or w<=0 or h<=0: raise RuntimeError("Invalid video metadata")
    return fps,w,h,frames,frames/fps if frames else 0


def frame_at(path,sec):
    cap=cv2.VideoCapture(str(path)); cap.set(cv2.CAP_PROP_POS_MSEC,max(0,float(sec))*1000); ok,fr=cap.read(); cap.release(); return fr if ok else None


def make_demo():
    path=UPLOAD_ROOT/"hunter_demo_v07.mp4"; fps=24; W,H=640,360; seconds=8; rng=np.random.default_rng(20260913)
    pos=np.column_stack([rng.uniform(100,540,18),rng.uniform(80,300,18)]); vel=rng.uniform(-3,3,(18,2))
    wr=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"mp4v"),fps,(W,H))
    if not wr.isOpened(): raise RuntimeError("Could not create demo")
    for k in range(fps*seconds):
        fr=np.zeros((H,W,3),np.uint8); fr[:]=(9,14,20); cv2.rectangle(fr,(75,50),(565,315),(75,95,115),2); pos+=vel+rng.normal(0,.1,pos.shape)
        for a,lo,hi in [(0,88,552),(1,63,302)]:
            hit=(pos[:,a]<lo)|(pos[:,a]>hi); vel[hit,a]*=-1; pos[:,a]=np.clip(pos[:,a],lo,hi)
        for i,(x,y) in enumerate(pos):
            cv2.circle(fr,(int(x),int(y)),10,(225,230,235),-1); cv2.putText(fr,str(i+1),(int(x)-6,int(y)+4),cv2.FONT_HERSHEY_SIMPLEX,.3,(15,20,25),1,cv2.LINE_AA)
        wr.write(fr)
    wr.release(); return path


with st.sidebar:
    st.markdown("### HUNTER")
    section=st.radio("Workspace",["Randomness Chamber","Video Intelligence","System Audit"],label_visibility="collapsed")
    st.divider(); st.caption("ENGINE STATE"); st.write("● 11 analytical roles"); st.write("● deterministic seeds"); st.write("● FDR + global null control"); st.write("● multi-window challenger"); st.write("● no random completion"); st.divider(); st.caption("Claim boundary"); st.caption("Hunter judges evidence against calibrated nulls. It does not claim lottery predictability.")

if section=="Randomness Chamber":
    st.subheader("Randomness Chamber")
    st.caption("The lottery is the stress chamber, not the objective. Hunter is judged by false positives, detection power, stability and challenger survival.")
    c1,c2,c3,c4=st.columns(4)
    trials=c1.select_slider("Null calibration",options=[80,120,180,240,320,500],value=240)
    n_draws=c2.select_slider("Draws",options=[100,150,250,400,600,1000,1500,2000],value=600)
    seed=c3.number_input("Seed",1,2_000_000_000,20260913)
    source=c4.selectbox("Evidence source",["Pure null","Frequency bias","Serial persistence","Regime shift","Periodic modulation","Paste historical draws"])
    strength=.30; text=""
    if source not in {"Pure null","Paste historical draws"}: strength=st.slider("Injected structure strength",0.05,0.80,0.30,0.05)
    if source=="Paste historical draws": text=st.text_area("One draw per line · exactly 6 numbers",height=180,placeholder="1 7 12 24 31 44\n...")
    cfg=HunterRandomnessConfig(monte_carlo_trials=int(trials),calibration_seed=918273)
    if st.button("RUN HUNTER ADJUDICATION",type="primary",use_container_width=True):
        try:
            if source=="Pure null": draws=generate_uniform_draws(int(n_draws),config=cfg,seed=int(seed))
            elif source=="Paste historical draws": draws=parse_draw_text(text,cfg)
            else:
                kind={"Frequency bias":"frequency_bias","Serial persistence":"serial_persistence","Regime shift":"regime_shift","Periodic modulation":"periodicity"}[source]
                draws=generate_alternative(int(n_draws),config=cfg,seed=int(seed),kind=kind,strength=float(strength))
            with st.status("Running calibrated specialist chamber…",expanded=True) as status:
                st.write("M1–M10 extracting separate evidence channels"); st.write("Monte Carlo null chamber calibrating family-wise evidence"); st.write("M11 challenger testing multi-window persistence"); result=analyze_hunter_randomness(draws,cfg); status.update(label="Hunter adjudication complete",state="complete")
            st.session_state["hunter_v07_result"]=result
        except Exception as ex: st.error(str(ex))
    r=st.session_state.get("hunter_v07_result")
    if r:
        verdict_panel(r); a,b,c,d=st.columns(4); a.metric("Global p",f"{r['global_p']:.4f}"); b.metric("Persistent",len(r["persistent_signals"])); c.metric("Fragile",len(r["fragile_signals"])); d.metric("Challenger","PASS" if r["challenger_pass"] else "CHALLENGE")
        st.markdown("#### Specialist evidence board"); specialist_grid(r); st.markdown("#### Cross-window evidence"); df=pd.DataFrame(r["windows"]); rename={k:k.split("_",1)[0] for k in df.columns if k.startswith("M")}; st.dataframe(df.rename(columns=rename).round(3),use_container_width=True,hide_index=True)
        with st.expander("Audit payload"): st.json({k:v for k,v in r.items() if k not in {"specialists","windows"}})
    st.divider(); st.markdown("#### Adversarial validation pack"); st.caption("Five known-truth chambers: one pure null and four injected alternatives. This measures behavior; it is not a prediction benchmark.")
    if st.button("RUN 5-CHAMBER VALIDATION",use_container_width=True):
        vcfg=HunterRandomnessConfig(monte_carlo_trials=min(int(trials),180),calibration_seed=918273)
        with st.status("Running adversarial validation…",expanded=True) as status: pack=validation_suite(vcfg,n_draws=min(int(n_draws),600),seed=int(seed)); status.update(label="Validation complete",state="complete")
        st.session_state["hunter_v07_pack"]=pack
    pack=st.session_state.get("hunter_v07_pack")
    if pack:
        rows=[{"scenario":x["scenario"],"truth":x["truth"],"verdict":x["verdict"],"global p":round(x["global_p"],4),"persistent":len(x["persistent_signals"]),"challenger":"PASS" if x["challenger_pass"] else "CHALLENGE"} for x in pack]; st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

elif section=="Video Intelligence":
    st.subheader("Video Intelligence"); st.caption(f"Preserved hardened video core {ENGINE_VERSION}. Pre-extraction evidence only; weak tracking or identity must abstain.")
    mode=st.radio("Video source",["Built-in controlled chamber","Upload video"],horizontal=True); path=None
    if mode=="Built-in controlled chamber":
        if st.button("CREATE CONTROLLED VIDEO",use_container_width=True): st.session_state["video_v07_path"]=str(make_demo())
        if st.session_state.get("video_v07_path"): path=Path(st.session_state["video_v07_path"])
    else:
        up=st.file_uploader("Video",type=["mp4","mov","m4v","avi"])
        if up:
            path=UPLOAD_ROOT/f"{int(time.time())}_{up.name}"; path.write_bytes(up.getbuffer()); st.session_state["video_v07_path"]=str(path)
    if path and path.exists():
        fps,W,H,frames,duration=video_meta(path); st.video(str(path)); a,b,c,d=st.columns(4); a.metric("FPS",f"{fps:.2f}"); b.metric("Resolution",f"{W}×{H}"); c.metric("Frames",frames); d.metric("Duration",f"{duration:.1f}s")
        cutoff=st.slider("Hard pre-extraction cutoff",0.2,max(0.3,float(duration)),min(float(duration),max(.5,float(duration)*.55)),0.1); chamber_x=st.slider("Chamber X %",0,100,(8,92)); chamber_y=st.slider("Chamber Y %",0,100,(8,92)); extract_x=st.slider("Extraction X %",0,100,(70,92)); extract_y=st.slider("Extraction Y %",0,100,(8,35)); chamber=(W*chamber_x[0]/100,H*chamber_y[0]/100,W*chamber_x[1]/100,H*chamber_y[1]/100); extraction=(W*extract_x[0]/100,H*extract_y[0]/100,W*extract_x[1]/100,H*extract_y[1]/100)
        fr=frame_at(path,cutoff)
        if fr is not None:
            preview=fr.copy(); cv2.rectangle(preview,(int(chamber[0]),int(chamber[1])),(int(chamber[2]),int(chamber[3])),(255,255,255),2); cv2.rectangle(preview,(int(extraction[0]),int(extraction[1])),(int(extraction[2]),int(extraction[3])),(0,255,255),2); st.image(cv2.cvtColor(preview,cv2.COLOR_BGR2RGB),caption="Exact cutoff frame · white chamber · yellow extraction zone")
        verified=st.checkbox("I verified this cutoff is before any winning ball enters the extraction path and before any result is visible.")
        if st.button("ANALYZE / LOCK EVIDENCE",type="primary",use_container_width=True,disabled=not verified):
            with st.status("Hunter measuring physical evidence…",expanded=True) as status:
                report=analyze_video(path,extraction_zone=extraction,chamber_roi=chamber,cutoff_seconds=float(cutoff),cutoff_verified_by_operator=True,recovery_dir="recovery",detector_config={"min_radius":5,"max_radius":34,"min_dist":10,"use_hough":True,"use_color_contours":True},tracker_config={"max_distance":35,"max_missed":8,"velocity_window":5,"radius_weight":.35,"max_radius_change":.65,"gap_growth":.20}); rp=RUN_ROOT/"hunter_v07_video.json"; save_report(report,rp); lp=lock_report(rp); status.update(label="Evidence frozen and SHA-256 locked",state="complete")
            st.session_state["video_v07_report"]=report; st.session_state["video_v07_lock"]=json.loads(Path(lp).read_text())
    rep=st.session_state.get("video_v07_report")
    if rep:
        st.markdown("#### Locked video outcome"); tq=rep.get("quality_gate",{}).get("trajectory",{}); iq=rep.get("quality_gate",{}).get("identity",{}); a,b,c,d=st.columns(4); a.metric("Status",rep.get("top6_status")); b.metric("Eligible tracks",tq.get("eligible_tracks",0)); c.metric("Numbered eligible",iq.get("numbered_eligible_tracks",0)); d.metric("Frames",rep.get("video",{}).get("frames_processed",0))
        if rep.get("top6_status")!="locked_candidate": st.warning("Hunter abstained rather than manufacturing an answer.")
        ranking=rep.get("anonymous_track_ranking",[]); agg={}; eligible=[x for x in ranking if x.get("trajectory_eligible")]; use=(eligible or ranking)[:20]
        for rec in use:
            for k,v in (rec.get("specialists",{}).get("scores") or {}).items(): agg.setdefault(k,[]).append(float(v))
        if agg: st.markdown("#### Current video specialist evidence"); st.dataframe(pd.DataFrame([{"specialist":k,"mean evidence":round(float(np.mean(v)),3),"n tracks":len(v)} for k,v in agg.items()]),use_container_width=True,hide_index=True)
        lock=st.session_state.get("video_v07_lock",{}); st.code(f"report SHA-256: {lock.get('report_sha256','')}\ninput SHA-256: {lock.get('input_sha256','')}\nconfig SHA-256: {lock.get('config_sha256','')}",language=None)

else:
    st.subheader("System Audit")
    st.markdown("""<div class="h-card"><b>Architecture rule:</b> Hunter is an evidence adjudicator, not a number generator. Randomness, video/physics, identity, nuisance rejection and the challenger are kept conceptually separate. An anomaly only survives when it clears calibrated null controls and stability checks.</div>""",unsafe_allow_html=True)
    st.markdown("#### Active layers"); st.dataframe(pd.DataFrame([["Randomness core","v0.7","10 null-calibrated statistical channels + M11 challenger"],["Video core",ENGINE_VERSION,"observation-centric tracking, OCR identity gates, physics/Markov/radiation, abstention"],["Audit","active","deterministic seeds, config/input/report hashes"],["Prediction fallback","disabled","no random completion"],["Scientific claim","restricted","software/benchmark validation only; no proven lottery edge"]],columns=["layer","version/state","role"]),use_container_width=True,hide_index=True)
    st.markdown("#### Specialist registry"); st.dataframe(pd.DataFrame([{"id":i,"role":n} for i,n in SPECIALISTS]),use_container_width=True,hide_index=True)
