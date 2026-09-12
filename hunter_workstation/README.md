# Hunter Workstation 0.5 — Saturday Lotto physics/video experiment

Hunter is an experimental **pre-extraction** measurement system for Saturday Lotto draw video. It is designed to be auditable, deterministic and conservative. The engine must not receive the actual result before the prediction is frozen, and it never fills missing numbers at random.

## Operator flow (iPhone friendly)

1. Open the repository's `hunter.html` launcher and create/open the `main` Codespace.
2. The devcontainer installs Python, FFmpeg and Tesseract, starts Streamlit automatically and forwards port **8501**. No terminal is required.
3. Upload one Saturday Lotto video.
4. Set the hard cutoff **before any winning ball enters the extraction path and before any result/winning-number graphic is visible**. Hunter shows the opening frame and the exact cutoff frame.
5. Adjust the chamber and extraction-path geometry. The `The Lott 2024/25` preset is only an initializer; the operator must verify the actual video.
6. Tick the explicit pre-extraction verification box. The Analyze button remains disabled until this is confirmed.
7. Press **Generate & lock PRE-EXTRACTION prediction**. Hunter writes `prediction.json` and a SHA-256 lock binding the input, configuration and report.
8. Only after the lock exists, enter the actual six numbers and score the already-frozen prediction.

## Engine layers

- Broadcast protection: chamber ROI, overlay masking and hard chronological **pre-extraction** cutoff.
- Ensemble ball detection: Hough circles plus saturated/round contour detection.
- Observation-centric deterministic multi-object tracking: short-horizon trajectory prediction is used for association only, with Hungarian assignment, short-occlusion tolerance and radius-consistency gating. Predicted points are never inserted as measured evidence.
- Trajectory quality control: point count, duration, continuity, radius stability, fragmentation and detections-per-frame are recorded. A numbered Top-6 is blocked if trajectory evidence is inadequate.
- Physical features: distance to extraction, approach velocity, speed, acceleration, dwell, circulation, track quality and collision candidates.
- Markov transition/absorption support (neutral unless a chronologically trained model is supplied).
- Probability-radiation propagation of track-state uncertainty.
- Conservative number identity: manual mapping > supplied probability matrix > OCR evidence, followed by one-to-one global assignment. OCR preprocessing variants from one frame count as correlated evidence, not independent observations; repeated support across independent frames is required. Weak evidence causes abstention.
- M1–M11 compatibility/fusion with current-video visual, motion, frequency, optical-nuisance, geometry, acoustic-envelope, conservative resonance-candidate, anomaly, propagation, relationship and challenger evidence.
- Recovered old state is used only as a reliability modifier. It never substitutes for current-video evidence.
- B0–B7 audit baselines. B0 is a theoretical fair-lottery reference only; it is **not** used to generate tickets.

## Output gate

Hunter returns one of three relevant Top-6 states:

- `locked_candidate` — at least six numbered identities exist on trajectory-eligible tracks and the report can be frozen.
- `insufficient_numbered_tracks` — trajectories are usable but fewer than six identities are supported.
- `tracking_quality_gate_failed` — tracking evidence itself is too weak or fragmented, so Hunter abstains even if a manual/automatic number map exists.

An abstention is a valid scientific outcome. Random completion is forbidden.

## Recovery boundary

The preserved v0.2.7 freeze is retained under `recovery/`. A later Drive-recovered v0.2.6 candidate source tree was inspected and tested, but its critical hashes do **not** match the frozen source hashes. Therefore Hunter does **not** claim byte-identical restoration of the old source. A sanitized aggregate reliability profile is included; raw recovered private session/video state is intentionally not published in this public repository.

Recovered specialist behavior is also treated conservatively: historical resonance/frequency, anomaly and audio/video association outputs are descriptive/heuristic evidence and do not establish physical causation or predictive power.

See `recovery/LEGACY_RECOVERY_MANIFEST.json` and `VALIDATION_REPORT.md`.

## Validation

Hunter v0.5 CI installs the same major runtime dependencies used by Codespaces and verifies Python compilation, FFmpeg, Tesseract, the full pytest suite, Streamlit startup and the `/_stcore/health` endpoint. Current branch validation completed **22/22 tests** and the Streamlit health smoke test successfully.

The repository validation report also records the original starter suite, recovered legacy suite, controlled laboratory history, and a real Saturday Lotto pre-extraction video audit. These validate software behavior and measurement controls; they do not establish an outcome-prediction edge.

## Scientific claim boundary

This is an experimental research system. It does not establish that physical video signals can predict lottery outcomes, and no predictive edge should be claimed without prospective, leakage-controlled evidence over multiple unseen draws. The next valid milestone is a series of reproducible, SHA-256-locked **pre-extraction** rankings evaluated only after each lock is created.