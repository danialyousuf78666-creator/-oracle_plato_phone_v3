# Hunter Workstation validation report

## Scope

Validation here establishes software behavior, reproducibility, leakage controls and recovery provenance. It does **not** establish a lottery predictive edge.

## Completed local validation

| Layer | Result | What it establishes |
|---|---:|---|
| Original Saturday physics/video starter | **11/11 tests passed** | Core starter pipeline components execute under the recovered package layout. |
| Drive-recovered v0.2.6 candidate | **15/15 tests passed** | Recovered candidate frequency gates, rolling-shutter gate, duration sampling, reproducibility and long-video planning behave as their tests specify. |
| Recovered controlled synthetic laboratory | **10/10 cases executed** | Flicker, pendulum, mixed motion, camera shake, rolling-shutter, A/V match, A/V lead, forced non-resonance, synthetic resonance and static-control cases all completed and produced reports. |
| Hunter 0.4 engine | **14/14 tests passed** | Masking, hashing, Markov, identity assignment, OCR evidence gates, recovery profile, locking, detection, cutoff, abstention, deterministic Top-6 with explicit identities, repeatability, scoring and frequency validation. |

## Recovery integrity finding

A genuine Drive-recovered v0.2.6 candidate source tree was found, together with a real-video `shared_memory.json` and `session_report.json`. However, all six checked critical candidate-source hashes differ from the hashes in the preserved v0.2.7 freeze. The candidate is therefore evidence of lineage and useful historical behavior, **not** a byte-identical restoration of the frozen source.

The public repository includes only a sanitized specialist reliability profile derived from recovered state. Raw recovered private session/video state is deliberately withheld from the public repository.

## Deployment gate

The authoritative deployment-environment gate is GitHub Actions `Hunter CI`. It must pass:

- Python compilation
- Hunter pytest suite
- FFmpeg availability
- Tesseract availability
- Streamlit startup and `/_stcore/health` response

## Prospective evaluation rule

For real Saturday Lotto work, every run must be generated and SHA-256 locked before the actual result is entered. Report Top-6 status/hits, Top-10 capture and Top-15 capture. An abstention is valid; random completion is forbidden. No post-reveal retuning of a run is permitted.
