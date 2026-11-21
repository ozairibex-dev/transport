#!/usr/bin/env bash
# One-command start for Mac/Linux.
#   ./start.sh          first run: sets everything up, then starts the app
#   ./start.sh demo     same, plus demo site/vendor/vehicles/drivers/employee
#   HTTPS=1 ./start.sh  serve a self-signed HTTPS certificate (phone GPS on same Wi-Fi)
set -e
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python) || { echo "Python 3.10+ is required: https://www.python.org/downloads/"; exit 1; }

if [ ! -d .venv ]; then
  echo "Creating virtual environment (.venv)..."
  "$PY" -m venv .venv
fi
source .venv/bin/activate

# Install/refresh libraries only when requirements.txt has changed
if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
  echo "Installing libraries..."
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
  [ "$HTTPS" = "1" ] && pip install -q cryptography
  touch .venv/.installed
fi

if [ "$1" = "demo" ]; then
  python -m flask --app app seed --demo
else
  python -m flask --app app seed
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$IP" ] && IP=$(ipconfig getifaddr en0 2>/dev/null || true)
SCHEME=http; [ "$HTTPS" = "1" ] && SCHEME=https
echo
echo "  App:              $SCHEME://localhost:5000"
[ -n "$IP" ] && echo "  Same Wi-Fi:       $SCHEME://$IP:5000"
echo "  Public HTTPS:     run 'cloudflared tunnel --url http://localhost:5000' in another terminal"
echo "  Stop:             Ctrl+C"
echo
python app.py
