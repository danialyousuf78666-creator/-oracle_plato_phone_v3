from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st

from hunter_engine import ENGINE_VERSION, MarkovModel, analyze_video, lock_report, save_report, score_locked_report

st.set_page_config(page_title="Hunter Workstation v0.5", page_icon="🎯", layout="wide")
st.markdown(
    """
    <style>
    .block-container{max-width:980px;padding-top:1.1rem;padding-bottom:4rem}
    div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.25);padding:.55rem .75rem;border-radius:14px}
    .hunter-note{padding:.85rem 1rem;border:1px solid rgba(128,128,128,.25);border-radius:14px;margin:.5rem 0 1rem}
    @media(max-width:640px){.block-container{padding-left:.65rem;padding-right:.65rem}.stButton button{min-height:52px}}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎯 Hunter Workstation v0.5")
st.caption(f"Saturday Lotto only • {ENGINE_VERSION} • deterministic pre-extraction experiment")
st.markdown(
    '<div class="hunter-note"><b>Scientific lock:</b> Hunter receives no actual result during analysis. '
    'Cut the video before any winning ball enters the extraction path and before any result graphic appears. '
    'Weak identity evidence causes abstention — never random completion.</div>',
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
    ok, first = cap.read()
    cap.release()
    if not ok or first is None or fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError("Video metadata/preview could not be decoded.")
    return fps, width, height, frames, (frames / fps if frames > 0 else 0.0), first


def frame_at_time(path: Path, seconds: float):
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(seconds)) * 1000.0)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


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
            raise ValueError("Each mask must be x0,y0,x1,y1")
        out.append(tuple(vals))
    return out


def parse_identity_map(text: str):
    if not (text or "").strip():
        return None
    raw = json.loads(text)
    out = {int(k): int(v) for k,v in raw.items()}
    if len(set(out.values())) != len(out):
        raise ValueError("The same ball number cannot be assigned to multiple tracks.")
    if any(v < 1 or v > 45 for v in out.values()):
        raise ValueError("Saturday Lotto numbers must be 1–45.")
    return out


video = st.file_uploader("1. Upload one Saturday Lotto draw video", type=["mp4","mov","m4v","avi","mkv","webm"])
if video is None:
    st.info("Upload a video. Hunter will show both the opening frame and the exact cutoff frame before it will run.")
    st.stop()

upload_root = Path("runs") / "uploads"
upload_root.mkdir(parents=True, exist_ok=True)
session_key = f"{len(video.getbuffer())}_{Path(video.name).name}"
if st.session_state.get("upload_key_v05") != session_key:
    p = upload_root / f"current{Path(video.name).suffix or '.mp4'}"
    p.write_bytes(video.getbuffer())
    st.session_state["upload_key_v05"] = session_key
    st.session_state["upload_path_v05"] = str(p)
    for k in ["report_v05","report_path_v05","lock_path_v05","lock_payload_v05"]:
        st.session_state.pop(k, None)

vp = Path(st.session_state["upload_path_v05"])
try:
    fps, width, height, total_frames, duration, first_frame = video_meta(vp)
except Exception as ex:
    st.error(str(ex)); st.stop()

c1,c2,c3,c4 = st.columns(4)
c1.metric("Duration", f"{duration:.1f}s" if duration else "unknown")
c2.metric("FPS", f"{fps:.2f}")
c3.metric("Frame", f"{width}×{height}")
c4.metric("Frames", f"{total_frames:,}")

st.subheader("2. Freeze a leakage-safe cutoff")
max_cutoff = max(0.2, duration if duration > 0 else 600.0)
# Conservative default: early enough for the common The Lott broadcast sequence.
default_cutoff = min(max_cutoff, 12.0 if max_cutoff >= 12.0 else max(0.2, max_cutoff * 0.50))
cutoff = st.number_input(
    "Hard cutoff in seconds — BEFORE extraction/outcome evidence",
    min_value=0.1, max_value=float(max_cutoff), value=float(default_cutoff), step=0.25,
)

preset = st.selectbox(
    "Broadcast geometry preset",
    ["The Lott 2024/25", "General / manual"],
    help="The preset only initializes geometry; always verify the two previews below.",
)
if preset == "The Lott 2024/25":
    chamber_x_default, chamber_y_default = (48,88), (12,94)
    extraction_x_default, extraction_y_default = (64,73), (18,85)
else:
    chamber_x_default, chamber_y_default = (5,95), (5,95)
    extraction_x_default, extraction_y_default = (65,85), (20,80)

p1,p2 = st.columns(2)
with p1:
    chamber_x = st.slider("Chamber horizontal (%)", 0, 100, chamber_x_default)
    chamber_y = st.slider("Chamber vertical (%)", 0, 100, chamber_y_default)
with p2:
    extraction_x = st.slider("Extraction-path horizontal (%)", 0, 100, extraction_x_default)
    extraction_y = st.slider("Extraction-path vertical (%)", 0, 100, extraction_y_default)

chamber_roi = pct_rect(chamber_x, chamber_y, width, height)
extraction_zone = pct_rect(extraction_x, extraction_y, width, height)

with st.expander("Advanced detector, identity and model controls"):
    auto_ocr = st.toggle("Conservative OCR + global one-to-one number assignment", value=True)
    ocr_every = st.slider("OCR interval (frames)", 2, 30, 8)
    identity_text = st.text_area("Optional manual track → number JSON", "", placeholder='{"1":7,"2":14,"3":23}')
    identity_prob_file = st.file_uploader("Optional external identity probability matrix JSON", type=["json"], key="id-prob-v05")
    markov_file = st.file_uploader("Optional chronologically trained Markov model JSON", type=["json"], key="markov-v05")
    radiation_weight = st.slider("Probability-radiation blend", 0.0, 0.25, 0.10, 0.01)
    specialist_weight = st.slider("M1–M11 fusion blend", 0.0, 0.40, 0.20, 0.01)
    min_radius = st.number_input("Min ball radius (px)", 2, 200, max(4, int(min(width,height)*0.006)))
    max_radius = st.number_input("Max ball radius (px)", 5, 300, max(16, int(min(width,height)*0.045)))
    hough_p2 = st.slider("Hough strictness (lower = more detections)", 12, 45, 20)
    max_distance = st.number_input("Association gate / max jump (px)", 10, 300, max(28, int(min(width,height)*0.045)))
    max_missed = st.number_input("Short-occlusion tolerance (frames)", 1, 20, 8)
    overlay_text = st.text_area("Optional overlay masks, one x0,y0,x1,y1 per line", "")

try:
    overlay_masks = parse_rect_lines(locals().get("overlay_text", ""))
    identity_map = parse_identity_map(locals().get("identity_text", ""))
except Exception as ex:
    st.error(f"Configuration error: {ex}"); st.stop()

cut_frame = frame_at_time(vp, min(float(cutoff), max(0.0, max_cutoff - 0.001)))
left,right = st.columns(2)
with left:
    st.image(draw_preview(first_frame, chamber_roi, extraction_zone, overlay_masks), caption="Opening frame — white chamber, yellow extraction path")
with right:
    if cut_frame is not None:
        st.image(draw_preview(cut_frame, chamber_roi, extraction_zone, overlay_masks), caption=f"CUT-OFF frame at {cutoff:.2f}s — this must contain no extraction/outcome evidence")
    else:
        st.warning("Could not decode the cutoff preview. Do not run until the cutoff can be verified.")

verified = st.checkbox(
    "I verified the CUT-OFF preview: no winning ball has entered the extraction path and no winning-number/result graphic is visible.",
    value=False,
)
st.caption("This confirmation is stored inside the hashed configuration. Changing the cutoff or geometry produces a different config SHA-256.")

st.subheader("3. Analyze and lock")
run_disabled = (not verified) or cut_frame is None
if st.button("Generate & lock PRE-EXTRACTION prediction", type="primary", use_container_width=True, disabled=run_disabled):
    run = Path("runs") / time.strftime("%Y%m%d_%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    input_copy = run / ("input" + (vp.suffix or ".mp4"))
    input_copy.write_bytes(vp.read_bytes())

    mm = None
    if locals().get("markov_file") is not None:
        mp = run / "markov.json"; mp.write_bytes(markov_file.getbuffer()); mm = MarkovModel.load(mp)
    identity_probs = None
    if locals().get("identity_prob_file") is not None:
        identity_probs = json.loads(identity_prob_file.getvalue().decode("utf-8"))

    detector_config = {
        "min_radius": int(locals().get("min_radius", 4)),
        "max_radius": int(locals().get("max_radius", 30)),
        "param2": float(locals().get("hough_p2", 20)),
        "use_color_contours": True,
    }
    tracker_config = {
        "max_distance": float(locals().get("max_distance", 35)),
        "max_missed": int(locals().get("max_missed", 8)),
        "velocity_window": 5,
        "radius_weight": 0.35,
        "max_radius_change": 0.65,
        "gap_growth": 0.20,
    }
    try:
        with st.status("Hunter v0.5 is measuring pre-extraction evidence…", expanded=True) as status:
            st.write("Observation-centric ball tracking + trajectory QC")
            report = analyze_video(
                input_copy,
                extraction_zone,
                identity_map=identity_map,
                identity_probs=identity_probs,
                markov_model=mm,
                chamber_roi=chamber_roi,
                overlay_masks=overlay_masks,
                cutoff_seconds=float(cutoff),
                radiation_weight=float(locals().get("radiation_weight", 0.10)),
                specialist_weight=float(locals().get("specialist_weight", 0.20)),
                recovery_dir="recovery",
                auto_ocr=bool(locals().get("auto_ocr", True)),
                ocr_every_n_frames=int(locals().get("ocr_every", 8)),
                detector_config=detector_config,
                tracker_config=tracker_config,
                cutoff_verified_by_operator=True,
            )
            st.write("Writing report and cryptographic lock")
            rp = run / "prediction.json"; save_report(report, rp)
            lp = lock_report(rp); lock_payload = json.loads(lp.read_text())
            status.update(label="PRE-EXTRACTION report frozen", state="complete")
        st.session_state.update(
            report_v05=report,
            report_path_v05=str(rp),
            lock_path_v05=str(lp),
            lock_payload_v05=lock_payload,
        )
    except Exception as ex:
        st.exception(ex); st.stop()

report = st.session_state.get("report_v05")
if report:
    st.divider(); st.subheader("Locked Hunter outcome")
    tq = report.get("quality_gate", {}).get("trajectory", {})
    iq = report.get("quality_gate", {}).get("identity", {})
    a,b,c,d = st.columns(4)
    a.metric("Status", report.get("top6_status"))
    b.metric("Eligible tracks", tq.get("eligible_tracks", 0))
    c.metric("Numbered eligible", iq.get("numbered_eligible_tracks", 0))
    d.metric("OCR evidence", report.get("ocr", {}).get("observations_total", 0))

    top6 = report.get("top6") or []
    if len(top6) == 6:
        st.success("Locked Top-6: " + "  •  ".join(str(x) for x in top6))
    else:
        st.warning("Hunter abstained. The evidence did not clear both trajectory and numbered-identity gates; no random numbers were inserted.")
        reasons = tq.get("reasons") or []
        if reasons:
            st.write("Trajectory gate: " + ", ".join(reasons))

    lp = st.session_state.get("lock_payload_v05") or {}
    st.code(
        f"report SHA-256: {lp.get('report_sha256','')}\n"
        f"input SHA-256:  {lp.get('input_sha256','')}\n"
        f"config SHA-256: {lp.get('config_sha256','')}",
        language=None,
    )

    rows=[]
    for i,r in enumerate(report.get("anonymous_track_ranking", []), 1):
        if i > 100: break
        bl=r.get("baselines", {})
        rows.append({
            "rank":i, "track":r.get("track_id"), "eligible":r.get("trajectory_eligible"),
            "number":r.get("number"), "points":r.get("n_points"), "OCR":r.get("ocr_observations"),
            "B1":round(bl.get("B1_distance",0),4), "B2":round(bl.get("B2_motion",0),4),
            "B4":round(bl.get("B4_physical_markov",0),4), "B5":round(bl.get("B5_plus_radiation",0),4),
            "B6":round(bl.get("B6_specialists",0),4), "B7":round(bl.get("B7_full_hybrid",0),4),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("Audit / QC / recovered-state diagnostics"):
        st.json({
            "protocol": report.get("protocol"), "detector": report.get("detector"),
            "tracker": {k:v for k,v in report.get("tracker",{}).items() if k != "quality"},
            "quality_gate": report.get("quality_gate"), "ocr": report.get("ocr"),
            "signals": report.get("signals"), "audit": report.get("audit"),
        })

    x,y = st.columns(2)
    with x:
        rp=Path(st.session_state["report_path_v05"])
        st.download_button("Download locked prediction", rp.read_bytes(), "hunter_v05_prediction.json", "application/json", use_container_width=True)
    with y:
        lpath=Path(st.session_state["lock_path_v05"])
        st.download_button("Download SHA-256 lock", lpath.read_bytes(), "hunter_v05_prediction.lock.json", "application/json", use_container_width=True)

    st.divider(); st.subheader("4. Reveal actual six numbers only after the lock")
    actual_text = st.text_input("Actual six winning numbers", placeholder="6,21,24,29,32,42")
    if st.button("Score the already-locked prediction", use_container_width=True):
        try:
            actual=[int(x.strip()) for x in actual_text.split(",") if x.strip()]
            score=score_locked_report(report, actual)
            st.json(score)
        except Exception as ex:
            st.error(str(ex))
