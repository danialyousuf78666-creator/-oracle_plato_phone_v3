from __future__ import annotations
import json,time
from pathlib import Path
import pandas as pd
import streamlit as st
from hunter_engine import analyze_video,save_report,lock_report,MarkovModel

st.set_page_config(page_title="Hunter Workstation",page_icon="🎯",layout="wide")
st.title("Hunter Workstation")
st.caption("Saturday Lotto • pre-extraction physical/video experiment • deterministic • no random completion")
with st.expander("Rules"):
    st.write("Chamber-only processing, hard pre-reveal cutoff, result overlays masked, track identity kept separate from numbered-ball identity, and SHA-256 lock before result comparison.")
video=st.file_uploader("Saturday Lotto video",type=["mp4","mov","m4v","avi"])
a,b,c=st.columns(3)
with a: chamber=st.text_input("Chamber ROI x0,y0,x1,y1","0,0,1920,1080")
with b: extraction=st.text_input("Extraction zone x0,y0,x1,y1","1400,200,1900,800")
with c: cutoff=st.number_input("Hard cutoff before reveal (seconds)",min_value=0.1,value=60.0,step=0.5)
d,e=st.columns(2)
with d: rw=st.slider("Probability-radiation weight",0.0,0.25,0.10,0.01)
with e: sw=st.slider("M1–M11 fusion weight",0.0,0.40,0.20,0.01)
identity_text=st.text_area("Optional track→number identity map JSON","{}",height=80,help='Example: {"1":7,"2":14,"3":23,"4":31,"5":38,"6":44}')
markov_file=st.file_uploader("Optional trained Markov model JSON",type=["json"],key="markov")
masks=st.text_area("Optional overlay/result masks; one rectangle per line","",height=65,help="x0,y0,x1,y1")

def rect(s):
    v=tuple(float(x.strip()) for x in s.split(","))
    if len(v)!=4:raise ValueError("rectangle requires four values")
    return v

if st.button("Generate & lock prediction",type="primary",use_container_width=True):
    if video is None:st.error("Upload a Saturday Lotto video first.");st.stop()
    try:
        chamber_roi=rect(chamber); extraction_zone=rect(extraction); overlay=[rect(x) for x in masks.splitlines() if x.strip()]; identity={int(k):int(v) for k,v in json.loads(identity_text or "{}").items()}
    except Exception as ex:st.error(f"Configuration error: {ex}");st.stop()
    run=Path("runs")/time.strftime("%Y%m%d_%H%M%S");run.mkdir(parents=True,exist_ok=True); vp=run/("input"+(Path(video.name).suffix or ".mp4"));vp.write_bytes(video.getbuffer())
    mm=None
    if markov_file is not None:
        mp=run/"markov.json";mp.write_bytes(markov_file.getbuffer());mm=MarkovModel.load(mp)
    with st.status("Running Hunter on pre-reveal footage…",expanded=True) as status:
        report=analyze_video(vp,extraction_zone,identity_map=identity or None,markov_model=mm,chamber_roi=chamber_roi,overlay_masks=overlay,cutoff_seconds=float(cutoff),radiation_weight=float(rw),specialist_weight=float(sw),recovery_dir="recovery")
        rp=run/"prediction.json";save_report(report,rp);lp=lock_report(rp);status.update(label="Prediction generated and SHA-256 locked",state="complete")
    st.session_state.update(report=report,report_path=str(rp),lock_path=str(lp))

report=st.session_state.get("report")
if report:
    st.subheader("Locked prediction")
    x,y,z=st.columns(3);x.metric("Status",report["top6_status"]);y.metric("Frames",report["frames_processed"]);z.metric("Identity",report["identity_mode"])
    st.markdown("### Top-6");st.write(report["top6"] or "No numbered Top-6: insufficient defensible numbered identities.")
    st.code(st.session_state.get("lock_path",""),language=None)
    rows=[]
    for i,r in enumerate(report["anonymous_track_ranking"],1):
        b=r.get("baselines",{});rows.append({"rank":i,"track":r["track_id"],"number":r.get("number"),"B1 distance":round(b.get("B1_distance",0),4),"B2 motion":round(b.get("B2_motion",0),4),"B4 +Markov":round(b.get("B4_physical_markov",0),4),"B5 +radiation":round(b.get("B5_plus_radiation",0),4),"B6 M1–M11":round(b.get("B6_specialists",0),4),"B7 hybrid":round(r.get("score",0),4)})
    if rows:st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    with st.expander("Recovery / audit"):st.json(report.get("audit",{}))
    st.divider();st.subheader("Reveal actual result only after lock");actual_text=st.text_input("Actual six winning numbers",placeholder="3,8,17,22,31,44")
    if st.button("Score locked prediction"):
        try:
            actual={int(x.strip()) for x in actual_text.split(",") if x.strip()}
            if len(actual)!=6:raise ValueError("enter exactly six unique numbers")
            pred=set(report.get("top6") or []); ranked=[r["number"] for r in report["anonymous_track_ranking"] if r.get("number") is not None]
            st.success(f"Locked Top-6 hits: {len(pred&actual)}/6");st.write({"Top-10 capture":len(actual&set(ranked[:10])),"Top-15 capture":len(actual&set(ranked[:15]))})
        except Exception as ex:st.error(str(ex))
