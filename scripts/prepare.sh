#!/usr/bin/env bash
# Verify the committed test keys, build the loader and make the variable store
# template in the work directory (default: lux-work in the home directory).
set -eu
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
python3 -m recorder prepare "$@"
