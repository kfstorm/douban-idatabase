#!/usr/bin/env bash

set -euo pipefail

# read the `--check` arg from the command line
check=false
if [ $# -gt 0 ] && [[ $1 == "--check" ]]; then
  check=true
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ "$check" == "true" ]]; then
  # Check formatting and linting without making changes
  uv run ruff check .
  uv run ruff format --check .
else
  # Fix issues and format code
  uv run ruff check --fix .
  uv run ruff format .
fi
