#!/usr/bin/env bash
# Run the unit tests. Set LUX_VM_TESTS=1 to include the tests that boot the
# virtual machine three times (needs a prepared work directory).
set -eu
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
python3 -m unittest discover -s recorder/tests -t .
