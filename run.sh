#!/usr/bin/env sh

set -euo pipefail

# Create a directory for Prometheus multiprocess metrics
export PROMETHEUS_MULTIPROC_DIR=$(mktemp -d /tmp/prometheus_multiproc.XXXXXX)
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
echo "Using Prometheus multiprocess directory: $PROMETHEUS_MULTIPROC_DIR"

# Clean up the metrics directory when the script exits
trap 'rm -rf "$PROMETHEUS_MULTIPROC_DIR"' EXIT

# Run the application with the environment built into the image. Do not invoke
# uv here, because it may synchronize the environment and require write access.
exec /.venv/bin/python -m app.main
