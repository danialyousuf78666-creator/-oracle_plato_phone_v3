# Hunter Workstation v0.5 validation report

## Scope

Validation here establishes software behavior, reproducibility, leakage controls, recovery provenance and measurement-pipeline robustness. It does **not** establish a Saturday Lotto predictive edge.

## Completed validation matrix

| Layer | Result | What it establishes |
|---|---:|---|
| Original Saturday physics/video starter | **11/11 tests passed** | Core starter pipeline components execute under the recovered package layout. |
| Drive-recovered legacy v0.2.6 candidate | **15/15 tests passed** | Candidate frequency gates, rolling-shutter gate, duration sampling, reproducibility and long-video planning behave as their own tests specify. |
| Preserved/recovered controlled laboratory history | **10/10 cases executed** | Flicker, pendulum, mixed/independent motion, camera shake, rolling shutter, A/V match, A/V lead, forced non-resonance, synthetic resonance and static-control cases all completed. |
| Hunter v0.5 GitHub CI | **22/22 tests passed** | Current exact branch code passes deterministic engine, masking, hashing, Markov, recovery, OCR, observation-centric tracking, quality-gate, cutoff, abstention, scoring and compatibility tests. |
| Runtime/toolchain | **PASS** | Python compilation passed; FFmpeg and Tesseract were available in CI. |
| Streamlit startup/health | **PASS** | `app_v05.py` started on port 8501 and `/_stcore/health` returned `ok`. |

The final green v0.5 branch validation was GitHub Actions run `34689935391` at branch head `4030c35296e25a50e547e0454a32bbca2dad462f` before documentation-only commits.

## Real Saturday Lotto pre-extraction audit

A real Saturday Lotto broadcast was retrieved from the user's `Hunter_workstation/Divideo` dataset: **Draw 4505, Saturday 21 September 2024**. The source video was 1280×720 at 25 fps, about 85.08 seconds long.

A strict **12.0 second cutoff** was selected by visual inspection because the chamber was already mixing balls while no winning ball had yet entered the extraction path and no winning-number/result graphic was present. This is deliberately stronger than a merely “pre-result-graphic” cutoff: already-extracted balls are outcome information even if the broadcaster has not displayed the number yet.

The recovered legacy specialist stack was then run on a chamber crop restricted to the first 12 seconds. Key observations were:

- M1 visual edge density: **0.182183**; evidence score **0.9883**.
- M2 apparent motion: mean dx **-0.0224 px/frame**, mean dy **-0.0108 px/frame**, mean magnitude **0.3505 px/frame**; score **0.1752**.
- M3 rejected the raw ~0.0833 Hz temporal component because there were too few cycles and multi-window instability; score **0.05**.
- M4 dominant brightness component **0.25 Hz**; rolling-shutter frequency gate blocked; slow drift score about **0.282**; specialist score **0.3922**.
- M5 coarse dominant edge orientation: **95°**; score **0.5**.
- M6 audio: dominant component about **453.12 Hz**, **53** onset events; score **0.9**. This is descriptive audio evidence, not physical-cause proof.
- M7 found a periodic candidate around **0.25 Hz** but did **not** establish resonance; score **0.3138**.
- M8 robust anomaly magnitude about **4.734**; score **0.6734**. An anomaly score is not evidence of unusual physics by itself.
- M9 remained insufficient for propagation from a single uncalibrated broadcast view.
- M10 brightness-motion lag correlation was about **0.3493** at -6 frames; A/V correlation about **0.2033** at -3 frames. Association is not causation.
- M11's strongest mundane explanation remained an optical/auto-exposure-type nuisance, consistent with the system's challenger role.

This real-video run is important because it demonstrates conservative falsification behavior: frequency/resonance/propagation claims were not promoted when the available pre-extraction evidence did not support them.

## Real tracking hardening result

The older/simple detector-tracker was highly fragmented on the same strict 12-second real chamber sequence. A representative run produced hundreds of tracks and could not support six reliable numbered identities.

The v0.5 observation-centric association prototype was compared under the same approximate detector conditions on a 150-frame pre-extraction chamber sequence:

| Metric | Simple tracker | v0.5 observation-centric prototype |
|---|---:|---:|
| Total tracks | 183 | 115 |
| Median measured points/track | 3 | 6 |
| Long tracks (≥1s) | 40 | 36 |
| Fragmentation index | ~4.575 | ~3.19 |

This is about a **37% reduction in total track fragmentation (183 → 115)** and a doubling of median measured track length (3 → 6) in that prototype comparison. It is a tracking-quality improvement, **not** evidence that the final selected numbers predict the draw.

## Identity hardening finding

Sparse OCR inspection of real pre-extraction ball crops produced plausible but noisy digits. It exposed a methodological weakness: multiple OCR preprocessing variants from the **same video frame** are correlated and must not count as repeated independent evidence.

Hunter v0.5 therefore collapses OCR variants to one strongest hypothesis per frame and requires repeated support across independent frames before a track can qualify for automatic number identity. A global one-to-one assignment is then applied. If six independent numbered identities are not supported, Hunter abstains.

On the inspected real pre-extraction material, six strong independent identities were **not yet established**. No Top-6 should be fabricated from that run.

## Observation-centric tracking rationale

The v0.5 tracker was hardened around an observation-centric principle: short-horizon motion is estimated from recent **measured observations**, while predicted positions are used only for association across brief occlusions. Predicted points are not inserted as physical evidence. This directly targets the failure mode seen in fast, nonlinear chamber motion, where last-position-only association fragments tracks badly.

## Recovery integrity finding

A genuine Drive-recovered v0.2.6 candidate source tree was found, together with real-video `shared_memory.json` and `session_report.json`. However, the checked critical candidate-source hashes differ from the hashes in the preserved v0.2.7 freeze. The candidate is therefore evidence of lineage and useful historical behavior, **not** a byte-identical restoration of the frozen source.

The public repository includes only a sanitized specialist reliability profile derived from recovered state. Raw recovered private session/video state is deliberately withheld from the public repository.

## Leakage and locking rules

Every valid real draw run must satisfy all of the following before analysis can be accepted:

1. Chamber ROI and extraction-path geometry are fixed.
2. The cutoff frame is inspected and is **before any winning ball enters the extraction path** and before any result graphic/winning number is visible.
3. The operator confirms the pre-extraction cutoff in the UI; this acknowledgement becomes part of the hashed configuration.
4. The engine runs without receiving actual winning numbers.
5. The input SHA-256, configuration SHA-256 and report SHA-256 are frozen.
6. Only after the lock exists may the actual six numbers be entered for scoring.
7. No random completion and no post-reveal adjustment are permitted.

The batch runner applies the same standard: it refuses to run unless supplied either a verified global cutoff or a per-video cutoff manifest plus the explicit `--verified-pre-extraction` acknowledgement.

## Predictive validation status

The Saturday experiment ledger currently has **zero completed locked/evaluated draws**. Therefore there is no honest basis yet for claiming an out-of-sample or prospective lottery edge.

The next valid milestone is not “force a Top-6.” It is to accumulate a chronological series of unseen, pre-extraction, SHA-256-locked runs and record, without retrospective selection:

- abstention rate and reasons;
- selected-ball rank;
- Top-6, Top-10 and Top-15 capture;
- 2+/3+/4+/5+/6 hit rates when a Top-6 exists;
- tracking/identity quality and stability;
- B0–B7 component comparisons;
- whether eventually extracted balls receive better pre-extraction ranking than non-extracted balls.

Until that evidence exists, Hunter v0.5 should be described as a **stronger, leakage-controlled experimental measurement and ranking system**, not a proven winning system.