from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st

from hunter_engine import (
    ENGINE_VERSION,
    MarkovModel,
    analyze_video,
    lock_report,
    save_report,
    score_locked_report,
)

st.set_page_config(page_title="Hunter Workstation", page_icon="🎯", layout="wide")

st.markdown(
    """
    <style>
      .block-container{max-width:980px;padding-top:1.25rem;padding-bottom:4rem}
      div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.25);padding:.55rem .75rem;border-radius:14px}
      .hunter-note{padding:.8rem 1rem;border:1px solid rgba(128,128,128,.22);border-radius:14px;margin:.4rem 0 1rem}
      @media(max-width:640px){.block-container{padding-left:.7rem;padding-right:.7rem}.stButton button{min-height:52px}}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎯 Hunter Workstation")
st.caption(f"Saturday Lotto • {ENGINE_VERSION} • deterministic pre-reveal video experiment • no random completion")
st.markdown(
    '<div class="hunter-note"><b>Rule:</b> Hunter must be locked before you reveal the actual draw result. '
    'If it cannot establish six numbered identities from the pre-reveal evidence, it abstains instead of inventing numbers.</div>',
    unsafe_allow_html=True,
)


def video_meta(path: Path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError("The uploaded video could not be opened.")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None or fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError("Video metadata/preview could not be decoded.")
    duration = frames / fps if frames > 0 else 0.0
    return fps, width, height, frames, duration, frame


def pct_rect(xrng, yrng, width, height):
    return (
        width * float(xrng[0]) / 100.0,
        height * float(yrng[0]) / 100.0,
        width * float(xrng[1]) / 100.0,
        height * float(yrng[1]) / 100.0,
    )


def draw_preview(frame, chamber, extraction, masks):
    out = frame.copy()
    x0,y0,x1,y1 = [int(round(v)) for v in chamber]
    cv2.rectangle(out, (x0,y0), (x1,y1), (255,255,255), 3)
    x0,y0,x1,y1 = [int(round(v)) for v in extraction]
    cv2.rectangle(out, (x0,y0), (x1,y1), (0,255,255), 3)
    for r in masks:
        x0,y0,x1,y1 = [int(round(v)) for v in r]
        cv2.rectangle(out, (x0,y0), (x1,y1), (0,0,255), -1)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


def parse_rect_lines(text: str):
    out = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        vals = [float(x.strip()) for x in line.split(",")]
        if len(vals) != 4:
            raise ValueError("Each overlay mask must be x0,y0,x1,y1")
        out.append(tuple(vals))
    return out


def parse_identity_map(text: str):
    if not (text or "").strip():
        return None
    raw = json.loads(text)
    out = {int(k): int(v) for k,v in raw.items()}
    if len(set(out.values())) != len(out):
        raise ValueError("Manual identity map cannot assign the same ball number to multiple tracks.")
    if any(v < 1 or v > 45 for v in out.values()):
        raise ValueError("Saturday Lotto numbers must be 1–45.")
    return out

video = st.file_uploader("1. Upload one Saturday Lotto draw video", type=["mp4","mov","m4v","avi","mkv","webm"])

if video is None:
    st.info("Upload a video first. Hunter will then show the pre-reveal controls and a frame preview.")
    with st.expander("What this build contains"):
        st.write("Ensemble ball detection, multi-object tracking, physical features, Markov propagation, probability radiation, conservative OCR/global identity assignment, M1–M11 recovery reliability, B0–B7 baselines, deterministic SHA-256 locking, and post-lock evaluation.")
    st.stop()

upload_root = Path("runs") / "uploads"
upload_root.mkdir(parents=True, exist_ok=True)
session_key = f"{len(video.getbuffer())}_{Path(video.name).name}"
if st.session_state.get("upload_key") != session_key:
    p = upload_root / f"current{Path(video.name).suffix or '.mp4'}"
    p.write_bytes(video.getbuffer())
    st.session_state["upload_key"] = session_key
    st.session_state["upload_path"] = str(p)
    st.session_state.pop("report", None)

vp = Path(st.session_state["upload_path"])
try:
    fps, width, height, total_frames, duration, first_frame = video_meta(vp)
except Exception as ex:
    st.error(str(ex)); st.stop()

m1,m2,m3,m4 = st.columns(4)
m1.metric("Duration", f"{duration:.1f}s" if duration else "unknown")
m2.metric("FPS", f"{fps:.2f}")
m3.metric("Size", f"{width}×{height}")
m4.metric("Frames", f"{total_frames:,}")

st.subheader("2. Protect the pre-reveal evidence")
max_cutoff = max(0.5, duration if duration > 0 else 600.0)
default_cutoff = min(max_cutoff, 60.0 if max_cutoff >= 60 else max(0.5, max_cutoff * 0.70))
cutoff = st.number_input(
    "Hard cutoff — stop analysis BEFORE the winning result is shown (seconds from video start)",
    min_value=0.1, max_value=float(max_cutoff), value=float(default_cutoff), step=0.5,
)

c1,c2 = st.columns(2)
with c1:
    chamber_x = st.slider("Chamber horizontal range (%)", 0, 100, (5,95))
    chamber_y = st.slider("Chamber vertical range (%)", 0, 100, (5,78))
with c2:
    extraction_x = st.slider("Extraction-zone horizontal range (%)", 0, 100, (72,96))
    extraction_y = st.slider("Extraction-zone vertical range (%)", 0, 100, (12,70))
chamber_roi = pct_rect(chamber_x, chamber_y, width, height)
extraction_zone = pct_rect(extraction_x, extraction_y, width, height)

with st.expander("Advanced controls — optional"):
    st.markdown("**Number identity**")
    auto_ocr = st.toggle("Automatic conservative number OCR + global one-to-one assignment", value=True)
    ocr_every = st.slider("OCR sampling interval (frames)", 2, 30, 8)
    identity_text = st.text_area("Manual track → number map JSON (overrides OCR when supplied)", "", placeholder='{"1":7,"2":14,"3":23,"4":31,"5":38,"6":44}')
    identity_prob_file = st.file_uploader("Optional external track↔number probability matrix JSON", type=["json"], key="identity-probs")
    st.markdown("**Physical model**")
    radiation_weight = st.slider("Probability-radiation blend", 0.0, 0.25, 0.10, 0.01)
    specialist_weight = st.slider("M1–M11 reliability/fusion blend", 0.0, 0.40, 0.20, 0.01)
    markov_file = st.file_uploader("Optional trained Markov transition model JSON", type=["json"], key="markov")
    st.markdown("**Detector / tracker**")
    d1,d2,d3 = st.columns(3)
    with d1: min_radius = st.number_input("Min ball radius (px)", 2, 200, max(3, int(min(width,height)*0.008)))
    with d2: max_radius = st.number_input("Max ball radius (px)", 5, 400, max(20, int(min(width,height)*0.08)))
    with d3: hough_p2 = st.slider("Hough sensitivity", 10, 50, 22, help="Lower detects more circles; higher is stricter.")
    t1,t2 = st.columns(2)
    with t1: max_distance = st.number_input("Tracker max jump (px)", 10, 300, max(30, int(min(width,height)*0.055)))
    with t2: max_missed = st.number_input("Tracker missed-frame tolerance", 1, 20, 4)
    overlay_text = st.text_area("Overlay/result masks in pixels; one x0,y0,x1,y1 rectangle per line", "", help="Use this only for broadcast graphics inside the chamber crop.")

try:
    overlay_masks = parse_rect_lines(locals().get("overlay_text", ""))
    identity_map = parse_identity_map(locals().get("identity_text", ""))
except Exception as ex:
    st.error(f"Advanced configuration error: {ex}"); st.stop()

st.image(draw_preview(first_frame, chamber_roi, extraction_zone, overlay_masks), caption="Preview: white = chamber ROI, yellow = extraction zone, red = masked overlay")
st.subheader("3. Generate and cryptographically lock the prediction")
st.caption("The actual winning result is not requested until after this lock exists.")

if st.button("Generate & lock prediction", type="primary", use_container_width=True):
    if cutoff >= max_cutoff and duration > 0:
        st.warning("Your cutoff reaches the end of the video. For a leakage-safe test, confirm that the winning result is not visible before this cutoff.")
    run = Path("runs") / time.strftime("%Y%m%d_%H%M%S"); run.mkdir(parents=True, exist_ok=True)
    input_copy = run / ("input" + (vp.suffix or ".mp4")); input_copy.write_bytes(vp.read_bytes())
    mm = None
    if locals().get("markov_file") is not None:
        mp = run / "markov.json"; mp.write_bytes(markov_file.getbuffer()); mm = MarkovModel.load(mp)
    identity_probs = None
    if locals().get("identity_prob_file") is not None:
        identity_probs = json.loads(identity_prob_file.getvalue().decode("utf-8"))
    detector_config = {
        "min_radius": int(locals().get("min_radius", max(3,int(min(width,height)*0.008)))),
        "max_radius": int(locals().get("max_radius", max(20,int(min(width,height)*0.08)))),
        "param2": float(locals().get("hough_p2",22)), "use_color_contours": True,
    }
    tracker_config = {"max_distance": float(locals().get("max_distance", max(30,int(min(width,height)*0.055)))), "max_missed": int(locals().get("max_missed",4))}
    try:
        with st.status("Hunter is measuring the pre-reveal footage…", expanded=True) as status:
            st.write("Detecting and tracking balls")
            report = analyze_video(
                input_copy, extraction_zone, identity_map=identity_map, identity_probs=identity_probs,
                markov_model=mm, chamber_roi=chamber_roi, overlay_masks=overlay_masks,
                cutoff_seconds=float(cutoff), radiation_weight=float(locals().get("radiation_weight",0.10)),
                specialist_weight=float(locals().get("specialist_weight",0.20)), recovery_dir="recovery",
                auto_ocr=bool(locals().get("auto_ocr",True)), ocr_every_n_frames=int(locals().get("ocr_every",8)),
                detector_config=detector_config, tracker_config=tracker_config,
            )
            st.write("Freezing report and SHA-256 evidence lock")
            rp = run / "prediction.json"; save_report(report, rp); lp = lock_report(rp); lock_payload = json.loads(lp.read_text())
            status.update(label="Prediction frozen — lock created", state="complete")
        st.session_state.update(report=report, report_path=str(rp), lock_path=str(lp), lock_payload=lock_payload)
    except Exception as ex:
        st.exception(ex); st.stop()

report = st.session_state.get("report")
if report:
    st.divider(); st.subheader("Locked Hunter outcome")
    a,b,c,d = st.columns(4)
    a.metric("Status", report.get("top6_status")); b.metric("Tracks", report.get("detector",{}).get("tracks_total",0)); c.metric("OCR evidence", report.get("ocr",{}).get("observations_total",0)); d.metric("Identity", report.get("identity_mode"))
    top6 = report.get("top6") or []
    if len(top6) == 6:
        st.success("Locked Top-6: " + "  •  ".join(str(x) for x in top6))
    else:
        st.warning("Hunter abstained from a numbered Top-6 because fewer than six track identities cleared the evidence gate. The physical ranking is still shown below; no random numbers were inserted.")
    lock_payload = st.session_state.get("lock_payload") or {}
    st.code(f"report SHA-256: {lock_payload.get('report_sha256','')}\ninput SHA-256:  {lock_payload.get('input_sha256','')}\nconfig SHA-256: {lock_payload.get('config_sha256','')}", language=None)
    rows=[]
    for i,r in enumerate(report.get("anonymous_track_ranking",[]),1):
        bline=r.get("baselines",{})
        rows.append({"rank":i,"track":r.get("track_id"),"number":r.get("number"),"points":r.get("n_points"),"OCR obs":r.get("ocr_observations"),"collisions":r.get("collision_candidates"),"B1 distance":round(bline.get("B1_distance",0),4),"B2 motion":round(bline.get("B2_motion",0),4),"B4 +Markov":round(bline.get("B4_physical_markov",0),4),"B5 +radiation":round(bline.get("B5_plus_radiation",0),4),"B6 M1–M11":round(bline.get("B6_specialists",0),4),"B7 hybrid":round(bline.get("B7_full_hybrid",0),4)})
    if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else: st.error("No usable ball tracks were detected. Adjust the chamber ROI and detector radius/sensitivity, then generate a new PRE-REVEAL run. Do not tune after looking at the actual result.")
    with st.expander("Diagnostics / recovered state"):
        st.json({"detector": report.get("detector"), "ocr": report.get("ocr"), "signals": report.get("signals"), "audit": report.get("audit")})
    col1,col2 = st.columns(2)
    with col1:
        rp = Path(st.session_state["report_path"]); st.download_button("Download locked prediction JSON", rp.read_bytes(), file_name="hunter_prediction.json", mime="application/json", use_container_width=True)
    with col2:
        lp = Path(st.session_state["lock_path"]); st.download_button("Download SHA-256 lock", lp.read_bytes(), file_name="hunter_prediction.lock.json", mime="application/json", use_container_width=True)
    st.divider(); st.subheader("4. Reveal the actual result only now")
    actual_text = st.text_input("Actual six winning numbers", placeholder="3,8,17,22,31,44")
    if st.button("Score the already-locked prediction", use_container_width=True):
        try:
            actual = [int(x.strip()) for x in actual_text.split(",") if x.strip()]; result = score_locked_report(report, actual)
            st.success(f"Locked Top-6 hits: {result['top6_hits']}/6")
            e1,e2,e3 = st.columns(3); e1.metric("Top-6 hits", result["top6_hits"]); e2.metric("Top-10 capture", result["top10_capture"]); e3.metric("Top-15 capture", result["top15_capture"])
        except Exception as ex:
            st.error(str(ex))
