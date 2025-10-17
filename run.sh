#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate

pip install -U pip
pip install -r requirements.txt

export FLASK_APP=app.py
export FLASK_RUN_HOST=0.0.0.0
export FLASK_RUN_PORT=5001

# Start Flask app in background
flask run &
FLASK_PID=$!

# Wait a moment for Flask to start up
sleep 3

# Open browser to the application
open "http://localhost:5001"

# Wait for Flask process to complete
wait $FLASK_PID

