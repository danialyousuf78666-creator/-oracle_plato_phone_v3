# Hunter Workstation 0.4 — Saturday Lotto physics/video experiment

Hunter is an experimental **pre-reveal** measurement system for Saturday Lotto draw video. It is designed to be auditable, deterministic and conservative: it must not see the actual result before the prediction is frozen, and it never fills missing numbers at random.

## Operator flow (iPhone friendly)

1. Open the repository's `hunter.html` launcher and create/open the `main` Codespace.
2. The devcontainer installs Python, FFmpeg and Tesseract, starts Streamlit automatically and forwards port **8501**. No terminal is required.
3. Upload one Saturday Lotto video.
4. Set the hard cutoff **before the winning result is visible**. Adjust the chamber ROI and extraction-zone sliders using the first-frame preview.
5. Press **Generate & lock prediction**. Hunter writes `prediction.json` and a SHA-256 lock binding the input, configuration and report.
6. Only after the lock exists, enter the actual six numbers and score the already-frozen prediction.

## Engine layers

- Broadcast protection: chamber ROI, overlay masking, hard chronological cutoff.
- Ensemble ball detection: Hough circles plus saturated/round contour detection.
- Deterministic Hungarian multi-object tracking.
- Physical features: distance to extraction, approach velocity, speed, acceleration, dwell, circulation, track quality and collision candidates.
- Markov transition/absorption support (neutral unless a trained chronological model is supplied).
- Probability-radiation propagation of track-state uncertainty.
- Conservative number identity: manual mapping > supplied probability matrix > OCR evidence, followed by one-to-one global assignment. It abstains if evidence is weak.
- M1–M11 compatibility/fusion with current-video visual, motion, frequency, optical-nuisance, geometry, acoustic-envelope, conservative resonance-candidate, anomaly, propagation, relationship and challenger evidence.
- Recovered old state is used only as a reliability modifier. It never substitutes for current-video evidence.
- B0–B7 audit baselines. B0 is a theoretical fair-lottery reference only; it is **not** used to generate tickets.

## Recovery boundary

The preserved v0.2.7 freeze is retained under `recovery/`. A later Drive-recovered v0.2.6 candidate source tree was inspected and tested, but its critical hashes do **not** match the frozen source hashes. Therefore Hunter does **not** claim byte-identical restoration of the old source. A sanitized aggregate reliability profile is included; raw recovered private session/video state is intentionally not published in this public repository.

See `recovery/LEGACY_RECOVERY_MANIFEST.json` and `VALIDATION_REPORT.md`.

## Validation

The current Hunter tests cover masking, deterministic hashing, Markov propagation, global identity assignment, OCR evidence gates, recovered reliability loading, detection, hard cutoff, no-random-completion behavior, direct-map Top-6, repeatability, post-lock scoring and conservative frequency validation.

GitHub Actions (`hunter-ci.yml`) installs the same runtime dependencies used by Codespaces and runs the Hunter test suite plus a Streamlit startup/health smoke test.

## Scientific claim boundary

This is an experimental research system. It does not establish that physical video signals can predict lottery outcomes, and no predictive edge should be claimed without prospective, leakage-controlled evidence. The strongest acceptable result before any such evidence is a reproducible pre-result ranking with transparent abstention and out-of-sample evaluation.
