#!/bin/bash

# Go to project root (where this script is located)
# run.sh
cd backend
gunicorn app:app --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT

# Activate virtual environment
source venv/bin/activate

python backend/app.py