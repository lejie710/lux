#!/usr/bin/env bash
# Run every test, including the ones that boot the virtual machine three times.
set -eu
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
export LUX_VM_TESTS=1
python3 -m unittest discover -s recorder/tests -t .
bash scripts/check-clean.sh
