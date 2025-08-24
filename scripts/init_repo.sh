#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv sync --all-extras

rm -f .git/hooks/pre-commit
ln -s ../../scripts/hooks/pre-commit .git/hooks/pre-commit
