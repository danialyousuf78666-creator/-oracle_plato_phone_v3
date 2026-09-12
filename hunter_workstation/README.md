# Hunter Workstation — Saturday Lotto only

Runnable user-test handover for the **pre-extraction physical/video experiment**. It does not claim a proven predictive edge.

## Included

- Chamber-only ROI, result/overlay masking and hard pre-reveal cutoff.
- Hough ball detection, multi-object Hungarian tracking, position / velocity / acceleration / direction proxies, extraction distance, dwell and circulation features.
- Markov extraction-state propagation (multi-step Chapman–Kolmogorov via repeated transition multiplication).
- Probability-radiation uncertainty propagation into the extraction zone.
- M1–M11 specialist Head/router contract: Visual, Motion, Frequency, Optical, Geometry, Acoustic, Resonance, Anomaly, Propagation, Relationship and Challenger.
- Recovery loader for `shared_memory.json`, `deep_signatures.jsonl`, `screen_signatures.jsonl` and the preserved v0.2.7 freeze manifest.
- B1–B7 deterministic control layers and final hybrid ranking.
- Number identity kept separate from track identity; no random completion.
- SHA-256 lock before result comparison.
- Streamlit operator UI on port 8501 and chronological batch runner.

## Recovery boundary

The preserved freeze proves the old architecture and critical file hashes. Missing historical source ZIPs or learned-state files are **not fabricated**. Drop genuine recovered state into `recovery/`; the app records SHA-256 metadata. M6/M7 remain neutral unless real audio/resonance evidence is available.

## Run in Codespaces

Open the `hunter-workstation` branch in Codespaces. The devcontainer installs dependencies and starts the UI. Open forwarded port **8501**.

Manual start:

```bash
cd hunter_workstation
pip install -r requirements.txt
bash start.sh
```

Batch:

```bash
python batch.py --input /path/to/Divideo --chamber-roi 0,0,1920,1080 --extraction-zone 1400,200,1900,800 --cutoff-seconds 60
```

For a numbered Top-6, provide a defensible track→ball-number map. Otherwise Hunter ranks anonymous physical tracks and returns `insufficient_numbered_tracks` rather than inventing lottery numbers.
