from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

import hunter_engine as h
from hunter_tracking import ObservationCentricTracker, is_eligible_track, tracking_quality_summary


def d(frame, x, y, r=10):
    return h.Detection(frame=frame, x=float(x), y=float(y), r=float(r), score=1.0, source="test")


def test_observation_tracker_reacquires_after_short_occlusion():
    tr = ObservationCentricTracker(max_distance=18, max_missed=4, velocity_window=4)
    for fi in range(6):
        tr.update([d(fi, 20 + 6*fi, 50)])
    # Two missing observations. No synthetic points should be inserted.
    tr.update([]); tr.update([])
    before = len(tr.tracks[0].points)
    assigned = tr.update([d(8, 20 + 6*8, 50)])
    assert assigned[0][0] == 1
    assert len(tr.tracks) == 1
    assert len(tr.tracks[0].points) == before + 1


def test_observation_prediction_beats_last_point_gate_for_fast_motion():
    tr = ObservationCentricTracker(max_distance=8, max_missed=3, velocity_window=4)
    tr.update([d(0, 10, 20)])
    tr.update([d(1, 17, 20)])
    tr.update([d(2, 24, 20)])
    # A last-point-only tracker with an 8 px gate would be marginal after a missed frame;
    # observation prediction lands at the expected continuation.
    tr.update([])
    assigned = tr.update([d(4, 38, 20)])
    assert assigned[0][0] == 1
    assert len(tr.tracks) == 1


def test_radius_gate_rejects_implausible_identity_jump():
    tr = ObservationCentricTracker(max_distance=30, max_missed=2, max_radius_change=0.40)
    tr.update([d(0, 30, 30, 10)])
    tr.update([d(1, 32, 30, 10)])
    tr.update([d(2, 34, 30, 25)])
    assert len(tr.tracks) == 2


def test_tracking_quality_gate_distinguishes_fragments_from_supported_tracks():
    tr = ObservationCentricTracker(max_distance=20, max_missed=2)
    # Six coherent tracks over 20 frames.
    for fi in range(20):
        tr.update([d(fi, 30 + i*25 + fi, 40 + i*10, 8+i*0.1) for i in range(6)])
    # One one-frame fragment far away.
    tr.update([d(20, 300, 200, 9)])
    q = tracking_quality_summary(tr.tracks, fps=20.0, frames_processed=21, detections_total=121)
    assert q["eligible_tracks"] >= 6
    assert q["trajectory_gate_pass"] is True
    supported = [t for t in tr.tracks if is_eligible_track(t, 20.0)]
    assert len(supported) >= 6
    assert not is_eligible_track(tr.tracks[-1], 20.0)


def _make_video(path: Path, frames=30, fps=15.0, w=480, hh=270):
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    wr = cv2.VideoWriter(str(path), fourcc, fps, (w,hh))
    assert wr.isOpened()
    colors=[(0,0,255),(0,180,255),(0,255,0),(255,0,0),(255,0,255),(255,255,0)]
    for fi in range(frames):
        frame=np.zeros((hh,w,3),np.uint8)
        for i,c in enumerate(colors):
            x=55+i*65+int(2.0*fi)
            y=70+i*24+int(3*np.sin(fi/4+i))
            cv2.circle(frame,(x,y),12,c,-1)
            cv2.circle(frame,(x,y),12,(255,255,255),1)
        wr.write(frame)
    wr.release()
    return path


def test_engine_v05_records_pre_extraction_protocol_and_qc(tmp_path):
    v=_make_video(tmp_path/"v.avi")
    report=h.analyze_video(
        v,
        (330,30,475,250),
        identity_map={1:4,2:11,3:19,4:27,5:36,6:44},
        chamber_roi=(0,0,480,270),
        cutoff_seconds=1.2,
        cutoff_verified_by_operator=True,
        recovery_dir=Path(__file__).resolve().parents[1]/"recovery",
        auto_ocr=False,
        detector_config={"min_radius":8,"max_radius":18,"param1":120,"param2":45,"use_color_contours":True},
        tracker_config={"max_distance":35,"max_missed":5,"velocity_window":5},
    )
    assert report["version"] == "hunter-workstation-0.5.0"
    assert report["protocol"]["actual_result_available_to_engine"] is False
    assert report["protocol"]["cutoff_verified_by_operator"] is True
    assert report["protocol"]["cutoff_policy"] == "pre_extraction_and_pre_result_required"
    assert report["tracker"]["type"] == "observation_centric_hungarian_v0_5"
    assert "quality_gate" in report
    assert report["random_ticket_fallback"] is False
    assert report["post_draw_adjustment"] is False


def test_quality_gate_prevents_numbered_output_from_fragments(tmp_path):
    v=_make_video(tmp_path/"short.avi",frames=3,fps=15.0)
    report=h.analyze_video(
        v,
        (330,30,475,250),
        identity_map={1:4,2:11,3:19,4:27,5:36,6:44},
        chamber_roi=(0,0,480,270),
        cutoff_seconds=0.2,
        cutoff_verified_by_operator=True,
        recovery_dir=Path(__file__).resolve().parents[1]/"recovery",
        auto_ocr=False,
        detector_config={"min_radius":8,"max_radius":18,"param1":120,"param2":45,"use_color_contours":True},
        tracker_config={"max_distance":35,"max_missed":3},
    )
    assert report["top6"] == []
    assert report["top6_status"] == "tracking_quality_gate_failed"
    assert report["quality_gate"]["top6_allowed"] is False
