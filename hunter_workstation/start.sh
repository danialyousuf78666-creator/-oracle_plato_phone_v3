#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p runs
if pgrep -f "streamlit run app_command_center.py" >/dev/null 2>&1; then
  echo "Hunter Command Center already running on port 8501"
  exit 0
fi
nohup python -m streamlit run app_command_center.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.fileWatcherType none \
  > runs/streamlit.log 2>&1 &
echo $! > runs/streamlit.pid
for _ in $(seq 1 45); do
  if python - <<'PY' >/dev/null 2>&1
import socket
s=socket.socket(); s.settimeout(.25); ok=s.connect_ex(('127.0.0.1',8501))==0; s.close(); raise SystemExit(0 if ok else 1)
PY
  then
    echo "Hunter Command Center ready on port 8501"
    exit 0
  fi
  sleep 1
done
echo "Hunter Command Center failed to become ready; inspect hunter_workstation/runs/streamlit.log" >&2
exit 1
