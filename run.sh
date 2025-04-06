#!/usr/bin/env sh

set -euo pipefail

# Run the application
uvicorn app.main:app --host 0.0.0.0
