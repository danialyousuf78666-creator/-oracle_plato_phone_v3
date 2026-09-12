from __future__ import annotations

import json
import re
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import requests
import streamlit as st

from hunter_engine import ENGINE_VERSION, analyze_video, lock_report, save_report, score_locked_report
from hunter_randomness import (
    RandomnessConfig,
    analyze_randomness,
    generate_structured_draws,
    generate_uniform_draws,
    parse_draw_text,
    quick_validation_pack,
)

APP_VERSION = "hunter-mobile-lab-0.6.0"
RUN_ROOT = Path("runs")
UPLOAD_ROOT = RUN_ROOT / "uploads"
RUN_ROOT.mkdir(parents=True, exist_ok=True)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Hunter Mobile Lab", page_icon="🎯", layout="wide")
st.markdown(
    """
    <style>
      .block-container{max-width:980px;padding-top:.85rem;padding-bottom:4rem}
      .hunter-card{border:1px solid rgba(128,128,128,.26);border-radius:16px;padding:.9rem 1rem;margin:.35rem 0 1rem}
      div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.24);padding:.5rem .7rem;border-radius:14px}
      div[data-testid="stTabs"] button{min-height:46px}
      @media(max-width:640px){
        .block-container{padding-left:.55rem;padding-right:.55rem;padding-top:.55rem}
        .stButton button,.stDownloadButton button{min-height:52px;font-size:1rem}
        div[data-testid="stMetric"]{padding:.45rem .5rem}
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎯 Hunter Mobile Lab")
st.caption(f"{APP_VERSION} • video engine {ENGINE_VERSION} • phone-first randomness and motion laboratory")
st.markdown(
    '<div class="hunter-card"><b>Purpose:</b> test whether Hunter can distinguish a random control from reproducible structure. '
    'Lottery data is used as a harsh laboratory; this interface does not assume lottery predictability.</div>',
    unsafe_allow_html=True,
)


def _video_meta(path: Path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError("The video could not be opened.")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    ok, first = cap.read()
    cap.release()
    if not ok or first is None or fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError("Video metadata or the first frame could not be decoded.")
    return fps, width, height, frames, (frames / fps if frames > 0 else 0.0), first


def _frame_at(path: Path, seconds: float):
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(seconds)) * 1000.0)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def _pct_rect(xrng, yrng, width, height):
    return (
        width * float(xrng[0]) / 100.0,
        height * float(yrng[0]) / 100.0,
        width * float(xrng[1]) / 100.0,
        height * float(yrng[1]) / 100.0,
    )


def _draw_preview(frame, chamber, extraction):
    out = frame.copy()
    x0, y0, x1, y1 = [int(round(v)) for v in chamber]
    cv2.rectangle(out, (x0, y0), (x1, y1), (255, 255, 255), 3)
    x0, y0, x1, y1 = [int(round(v)) for v in extraction]
    cv2.rectangle(out, (x0, y0), (x1, y1), (0, 255, 255), 3)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


def _reset_video_report():
    for key in ["report_final", "report_path_final", "lock_path_final", "lock_payload_final"]:
        st.session_state.pop(key, None)


def _set_video_path(path: Path, source_label: str):
    st.session_state["video_path_final"] = str(path)
    st.session_state["video_source_final"] = source_label
    _reset_video_report()


def _drive_file_id(url: str) -> str | None:
    for pattern in [r"/file/d/([^/]+)", r"[?&]id=([^&]+)"]:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _stream_response_to_file(response, destination: Path, max_bytes: int = 700 * 1024 * 1024):
    total = 0
    with destination.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                fh.close()
                destination.unlink(missing_ok=True)
                raise ValueError("Video is larger than the 700 MB mobile-lab limit.")
            fh.write(chunk)
    if total < 1024:
        destination.unlink(missing_ok=True)
        raise ValueError("The downloaded file is too small to be a usable video.")


def _download_public_drive(url: str, destination: Path):
    file_id = _drive_file_id(url)
    if not file_id:
        raise ValueError("Could not read the Google Drive file ID from that link.")
    direct = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    with requests.get(direct, stream=True, timeout=(15, 180), allow_redirects=True) as response:
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" in content_type:
            raise ValueError("Google Drive returned a sign-in/permission page. Set the video to Anyone with the link, or use Upload from device.")
        _stream_response_to_file(response, destination)


def _download_youtube(url: str, destination: Path):
    try:
        import yt_dlp
    except Exception as ex:
        raise RuntimeError("YouTube support is not installed in this build yet.") from ex
    outtmpl = str(destination.with_suffix(".%(ext)s"))
    opts = {
        "format": "bv*[height<=720]+ba/b[height<=720]/best[height<=720]/best",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        candidate = Path(ydl.prepare_filename(info))
    for path in [destination.with_suffix(".mp4"), candidate]:
        if path.exists() and path.stat().st_size > 1024:
            if path != destination:
                path.replace(destination)
            return
    raise RuntimeError("YouTube download finished without producing a usable video file.")


def _download_video_link(url: str) -> Path:
    url = (url or "").strip()
    if not url.startswith("https://"):
        raise ValueError("Use an HTTPS YouTube or public Google Drive link.")
    destination = UPLOAD_ROOT / f"link_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
    lower = url.lower()
    if "youtube.com/" in lower or "youtu.be/" in lower:
        _download_youtube(url, destination)
    elif "drive.google.com/" in lower:
        _download_public_drive(url, destination)
    else:
        raise ValueError("For safety, link mode currently accepts YouTube or public Google Drive links only.")
    return destination


def _make_synthetic_video() -> Path:
    destination = UPLOAD_ROOT / "hunter_synthetic_demo.mp4"
    fps = 24
    seconds = 8
    width, height = 640, 360
    rng = np.random.default_rng(20260913)
    n = 15
    radius = 10
    pos = np.column_stack([rng.uniform(90, width - 90, n), rng.uniform(75, height - 65, n)])
    vel = rng.uniform(-2.6, 2.6, size=(n, 2))
    small = np.linalg.norm(vel, axis=1) < 1.2
    vel[small, 0] += 1.7
    writer = cv2.VideoWriter(str(destination), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Could not create the built-in demo video.")
    for frame_idx in range(fps * seconds):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (18, 18, 22)
        cv2.rectangle(frame, (65, 45), (width - 65, height - 40), (80, 80, 90), 2)
        pos += vel + rng.normal(0, 0.12, size=pos.shape)
        for axis, lo, hi in [(0, 75 + radius, width - 75 - radius), (1, 55 + radius, height - 50 - radius)]:
            hit = (pos[:, axis] < lo) | (pos[:, axis] > hi)
            vel[hit, axis] *= -1
            pos[:, axis] = np.clip(pos[:, axis], lo, hi)
        for i, (x, y) in enumerate(pos):
            cv2.circle(frame, (int(x), int(y)), radius, (225, 225, 225), -1)
            cv2.circle(frame, (int(x), int(y)), radius, (70, 70, 70), 1)
            cv2.putText(frame, str(i + 1), (int(x) - 6, int(y) + 4), cv2.FONT_HERSHEY_SIMPLEX, .32, (20, 20, 20), 1, cv2.LINE_AA)
        gain = 0.90 + 0.08 * np.sin(frame_idx / fps * 2 * np.pi * 0.7)
        writer.write(np.clip(frame.astype(np.float32) * gain, 0, 255).astype(np.uint8))
    writer.release()
    if not destination.exists() or destination.stat().st_size < 1024:
        raise RuntimeError("Built-in demo video generation failed.")
    return destination


def _show_randomness_result(result: dict):
    if result["verdict"] == "consistent_with_randomness":
        st.success(result["label"])
    elif result["verdict"] == "inconclusive":
        st.warning(result["label"])
    else:
        st.error(result["label"])
    a, b, c, d = st.columns(4)
    a.metric("Omnibus p", f"{result['omnibus_p']:.4f}")
    b.metric("Strongest signal", result["strongest_component"].replace("_", " "))
    c.metric("Strongest z", f"{result['strongest_z']:.2f}")
    d.metric("Draws", f"{result['n_draws']:,}")
    metrics = result["metrics"]
    st.dataframe(
        pd.DataFrame([
            {"diagnostic": "Frequency chi-square", "value": round(metrics["frequency_chi2"], 4), "z": round(result["component_z"]["frequency"], 3)},
            {"diagnostic": "Consecutive overlap", "value": round(metrics["mean_consecutive_overlap"], 4), "z": round(result["component_z"]["consecutive_overlap"], 3)},
            {"diagnostic": "Lag-1 dependence", "value": round(metrics["max_lag1_abs"], 4), "z": round(result["component_z"]["lag1_dependence"], 3)},
            {"diagnostic": "Pair recurrence", "value": round(metrics["pair_collision"], 1), "z": round(result["component_z"]["pair_recurrence"], 3)},
            {"diagnostic": "Normalized entropy", "value": round(metrics["normalized_entropy"], 6), "z": None},
        ]),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(result["claim_boundary"])


random_tab, video_tab = st.tabs(["🧪 Randomness Lab", "🎥 Video Analyzer"])

with random_tab:
    st.subheader("One-tap control test")
    st.write("The machine should leave a genuine random control alone, but react to injected structure.")
    if st.button("Run final 3-part validation", type="primary", use_container_width=True, key="validation-pack"):
        with st.status("Running deterministic Monte Carlo controls…", expanded=True) as status:
            pack = quick_validation_pack(
                n_draws=600,
                seed=20260913,
                config=RandomnessConfig(monte_carlo_trials=300, calibration_seed=918273),
            )
            status.update(label="Validation pack complete", state="complete")
        st.session_state["random_pack_final"] = pack

    pack = st.session_state.get("random_pack_final")
    if pack:
        rows = []
        for result in pack:
            rows.append({
                "scenario": result["scenario"],
                "known truth": result["truth"],
                "Hunter verdict": result["label"],
                "p": round(result["omnibus_p"], 4),
                "strongest": result["strongest_component"],
                "z": round(result["strongest_z"], 2),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        null_ok = pack[0]["verdict"] in {"consistent_with_randomness", "inconclusive"}
        structured_ok = all(r["verdict"] in {"departure_detected", "strong_departure_detected"} for r in pack[1:])
        if null_ok and structured_ok:
            st.success("Control behavior passed: no forced pattern claim on the random control, and both injected structures were detected.")
        else:
            st.warning("At least one control did not separate cleanly. Treat this run as diagnostic, not proof of reliability.")

    st.divider()
    st.subheader("Custom lottery-number laboratory")
    mode = st.radio(
        "Data source",
        ["Pure random simulation", "Injected structure", "Paste historical draws"],
        horizontal=True,
        key="random-source",
    )
    config = RandomnessConfig(monte_carlo_trials=300, calibration_seed=918273)
    if mode == "Pure random simulation":
        n_draws = st.slider("Number of draws", 100, 2000, 600, 100, key="rnd-n")
        seed = st.number_input("Simulation seed", 1, 2_000_000_000, 12345, 1, key="rnd-seed")
        if st.button("Judge random control", use_container_width=True):
            st.session_state["random_result_final"] = analyze_randomness(generate_uniform_draws(int(n_draws), seed=int(seed)), config)
    elif mode == "Injected structure":
        n_draws = st.slider("Number of draws", 100, 2000, 600, 100, key="str-n")
        bias_pct = st.slider("Relative frequency bias on number 7", 0, 200, 100, 5, key="str-bias")
        persistence_pct = st.slider("Serial persistence", 0, 50, 0, 1, key="str-pers")
        seed = st.number_input("Simulation seed", 1, 2_000_000_000, 23456, 1, key="str-seed")
        if st.button("Inject structure and test", use_container_width=True):
            draws = generate_structured_draws(
                int(n_draws),
                seed=int(seed),
                relative_bias=float(bias_pct) / 100.0,
                persistence=float(persistence_pct) / 100.0,
            )
            st.session_state["random_result_final"] = analyze_randomness(draws, config)
    else:
        history_text = st.text_area(
            "Paste one Saturday Lotto draw per line (6 numbers, 1–45)",
            height=180,
            placeholder="1, 7, 14, 22, 31, 45\n3, 9, 18, 24, 30, 41\n…",
        )
        if st.button("Judge pasted history", use_container_width=True):
            try:
                st.session_state["random_result_final"] = analyze_randomness(parse_draw_text(history_text), config)
            except Exception as ex:
                st.error(str(ex))

    if st.session_state.get("random_result_final"):
        st.divider()
        _show_randomness_result(st.session_state["random_result_final"])

with video_tab:
    st.subheader("Load a video without being forced into Files")
    source = st.radio(
        "Choose how to load the video",
        ["Paste video link", "Built-in demo", "Upload from device"],
        horizontal=True,
        key="video-source-mode",
    )

    if source == "Paste video link":
        st.caption("Accepts a YouTube URL or a public Google Drive video set to Anyone with the link.")
        video_url = st.text_input("YouTube or public Google Drive link", placeholder="https://youtube.com/watch?v=…")
        if st.button("Load video link", type="primary", use_container_width=True):
            try:
                with st.status("Fetching video…", expanded=True) as status:
                    path = _download_video_link(video_url)
                    status.update(label="Video loaded", state="complete")
                _set_video_path(path, "link")
                st.rerun()
            except Exception as ex:
                st.error(str(ex))
    elif source == "Built-in demo":
        st.write("No upload required. This creates a deterministic eight-second chamber simulation so you can verify the workflow immediately.")
        if st.button("Create and load demo", type="primary", use_container_width=True):
            try:
                _set_video_path(_make_synthetic_video(), "synthetic_demo")
                st.rerun()
            except Exception as ex:
                st.error(str(ex))
    else:
        st.caption("Use this only when you want iPhone Files/Photos. The other two modes avoid the device picker entirely.")
        upload = st.file_uploader("Choose video", type=["mp4", "mov", "m4v", "avi", "mkv", "webm"], key="mobile-upload")
        if upload is not None:
            key = f"{len(upload.getbuffer())}_{Path(upload.name).name}"
            if st.session_state.get("upload_key_final") != key:
                path = UPLOAD_ROOT / f"device_{int(time.time())}{Path(upload.name).suffix or '.mp4'}"
                path.write_bytes(upload.getbuffer())
                st.session_state["upload_key_final"] = key
                _set_video_path(path, "device")
                st.rerun()

    video_path_text = st.session_state.get("video_path_final")
    if not video_path_text:
        st.info("Choose Paste video link or Built-in demo. You do not need to open Files unless you select Upload from device.")
    else:
        vp = Path(video_path_text)
        if not vp.exists():
            st.session_state.pop("video_path_final", None)
            st.warning("The temporary video expired. Load it again.")
        else:
            st.success(f"Video ready • source: {st.session_state.get('video_source_final', 'unknown')}")
            try:
                fps, width, height, total_frames, duration, first_frame = _video_meta(vp)
            except Exception as ex:
                st.error(str(ex))
                st.stop()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Duration", f"{duration:.1f}s")
            c2.metric("FPS", f"{fps:.2f}")
            c3.metric("Frame", f"{width}×{height}")
            c4.metric("Frames", f"{total_frames:,}")

            st.subheader("Cutoff and chamber")
            is_demo = st.session_state.get("video_source_final") == "synthetic_demo"
            max_cutoff = max(0.2, duration)
            default_cutoff = min(max_cutoff - 0.01 if max_cutoff > 0.21 else max_cutoff, 7.5 if is_demo else 12.0)
            default_cutoff = max(0.1, default_cutoff)
            cutoff = st.number_input(
                "Hard cutoff in seconds — before extraction/result evidence",
                min_value=0.1,
                max_value=float(max_cutoff),
                value=float(default_cutoff),
                step=0.25,
            )

            if is_demo:
                chamber_x_default, chamber_y_default = (10, 90), (12, 90)
                extraction_x_default, extraction_y_default = (78, 90), (15, 60)
            else:
                chamber_x_default, chamber_y_default = (48, 88), (12, 94)
                extraction_x_default, extraction_y_default = (64, 73), (18, 85)

            with st.expander("Geometry / detector controls", expanded=False):
                p1, p2 = st.columns(2)
                with p1:
                    chamber_x = st.slider("Chamber horizontal (%)", 0, 100, chamber_x_default)
                    chamber_y = st.slider("Chamber vertical (%)", 0, 100, chamber_y_default)
                with p2:
                    extraction_x = st.slider("Extraction horizontal (%)", 0, 100, extraction_x_default)
                    extraction_y = st.slider("Extraction vertical (%)", 0, 100, extraction_y_default)
                min_radius = st.number_input("Min ball radius (px)", 2, 200, max(4, int(min(width, height) * 0.006)))
                max_radius = st.number_input("Max ball radius (px)", 5, 300, max(16, int(min(width, height) * 0.045)))
                hough_p2 = st.slider("Hough strictness", 12, 45, 20)
                max_distance = st.number_input("Tracking max jump (px)", 10, 300, max(28, int(min(width, height) * 0.045)))
                max_missed = st.number_input("Short occlusion tolerance", 1, 20, 8)

            chamber_roi = _pct_rect(chamber_x, chamber_y, width, height)
            extraction_zone = _pct_rect(extraction_x, extraction_y, width, height)
            cut_frame = _frame_at(vp, min(float(cutoff), max(0.0, duration - 0.001)))

            left, right = st.columns(2)
            with left:
                st.image(_draw_preview(first_frame, chamber_roi, extraction_zone), caption="Opening frame")
            with right:
                if cut_frame is not None:
                    st.image(_draw_preview(cut_frame, chamber_roi, extraction_zone), caption=f"Cutoff frame at {cutoff:.2f}s")
                else:
                    st.warning("Cutoff frame could not be decoded.")

            if is_demo:
                verified = True
                st.info("Built-in demo is outcome-free by construction, so the cutoff is automatically verified.")
            else:
                verified = st.checkbox(
                    "I verified the cutoff: no winning ball is in the extraction path and no result graphic is visible.",
                    value=False,
                )

            if st.button(
                "Analyze and lock Hunter outcome",
                type="primary",
                use_container_width=True,
                disabled=(not verified) or cut_frame is None,
            ):
                run = RUN_ROOT / time.strftime("%Y%m%d_%H%M%S")
                run.mkdir(parents=True, exist_ok=True)
                input_copy = run / ("input" + (vp.suffix or ".mp4"))
                input_copy.write_bytes(vp.read_bytes())
                detector_config = {
                    "min_radius": int(min_radius),
                    "max_radius": int(max_radius),
                    "param2": float(hough_p2),
                    "use_color_contours": True,
                }
                tracker_config = {
                    "max_distance": float(max_distance),
                    "max_missed": int(max_missed),
                    "velocity_window": 5,
                    "radius_weight": 0.35,
                    "max_radius_change": 0.65,
                    "gap_growth": 0.20,
                }
                try:
                    with st.status("Hunter is measuring pre-extraction evidence…", expanded=True) as status:
                        report = analyze_video(
                            input_copy,
                            extraction_zone,
                            identity_map=None,
                            identity_probs=None,
                            markov_model=None,
                            chamber_roi=chamber_roi,
                            overlay_masks=[],
                            cutoff_seconds=float(cutoff),
                            radiation_weight=0.10,
                            specialist_weight=0.20,
                            recovery_dir="recovery",
                            auto_ocr=not is_demo,
                            ocr_every_n_frames=8,
                            detector_config=detector_config,
                            tracker_config=tracker_config,
                            cutoff_verified_by_operator=True,
                        )
                        rp = run / "prediction.json"
                        save_report(report, rp)
                        lp = lock_report(rp)
                        lock_payload = json.loads(lp.read_text())
                        status.update(label="Hunter report locked", state="complete")
                    st.session_state.update(
                        report_final=report,
                        report_path_final=str(rp),
                        lock_path_final=str(lp),
                        lock_payload_final=lock_payload,
                    )
                    st.rerun()
                except Exception as ex:
                    st.exception(ex)

            report = st.session_state.get("report_final")
            if report:
                st.divider()
                st.subheader("Locked Hunter outcome")
                tq = report.get("quality_gate", {}).get("trajectory", {})
                iq = report.get("quality_gate", {}).get("identity", {})
                a, b, c, d = st.columns(4)
                a.metric("Status", report.get("top6_status"))
                b.metric("Eligible tracks", tq.get("eligible_tracks", 0))
                c.metric("Numbered eligible", iq.get("numbered_eligible_tracks", 0))
                d.metric("OCR evidence", report.get("ocr", {}).get("observations_total", 0))
                top6 = report.get("top6") or []
                if len(top6) == 6:
                    st.success("Locked Top-6: " + " • ".join(str(x) for x in top6))
                else:
                    st.warning("Hunter abstained because evidence did not clear the gates. No random numbers were inserted.")
                lock_payload = st.session_state.get("lock_payload_final") or {}
                st.code(
                    f"report SHA-256: {lock_payload.get('report_sha256', '')}\n"
                    f"input SHA-256:  {lock_payload.get('input_sha256', '')}\n"
                    f"config SHA-256: {lock_payload.get('config_sha256', '')}",
                    language=None,
                )

                rows = []
                for i, r in enumerate(report.get("anonymous_track_ranking", [])[:50], 1):
                    bl = r.get("baselines", {})
                    rows.append({
                        "rank": i,
                        "track": r.get("track_id"),
                        "eligible": r.get("trajectory_eligible"),
                        "number": r.get("number"),
                        "points": r.get("n_points"),
                        "B1": round(bl.get("B1_distance", 0), 4),
                        "B2": round(bl.get("B2_motion", 0), 4),
                        "B4": round(bl.get("B4_physical_markov", 0), 4),
                        "B7": round(bl.get("B7_full_hybrid", 0), 4),
                    })
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                x, y = st.columns(2)
                rp = Path(st.session_state["report_path_final"])
                lp = Path(st.session_state["lock_path_final"])
                with x:
                    st.download_button("Download locked report", rp.read_bytes(), "hunter_locked_prediction.json", "application/json", use_container_width=True)
                with y:
                    st.download_button("Download SHA-256 lock", lp.read_bytes(), "hunter_prediction.lock.json", "application/json", use_container_width=True)

                st.subheader("Reveal actual six only after lock")
                actual_text = st.text_input("Actual six winning numbers", placeholder="6,21,24,29,32,42")
                if st.button("Score locked outcome", use_container_width=True):
                    try:
                        actual = [int(x.strip()) for x in actual_text.split(",") if x.strip()]
                        st.json(score_locked_report(report, actual))
                    except Exception as ex:
                        st.error(str(ex))

st.caption("Hunter separates measurement from claims: weak evidence may correctly produce an abstention.")
