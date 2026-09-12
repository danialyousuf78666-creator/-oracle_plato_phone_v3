#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p runs
if pgrep -f "streamlit run app.py" >/dev/null 2>&1; then exit 0; fi
nohup python -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 > runs/streamlit.log 2>&1 &
echo "Hunter Workstation starting on port 8501"
