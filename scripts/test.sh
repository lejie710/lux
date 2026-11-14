#!/usr/bin/env bash
# Run the unit tests. Set LUX_VM_TESTS=1 to include the test that boots the
# virtual machine twice (needs a prepared work directory).
set -eu
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
python3 -m unittest discover -s recorder/tests -t .
