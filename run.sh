#!/bin/bash

# Go to project root (where this script is located)
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

python backend/app.py