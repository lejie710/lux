#!/usr/bin/env bash
# Record the runs that are allowed without a prediction: the normal run twice
# and the declared pilot e2 (one content byte of the loader changed, Secure
# Boot on). Then compare them. Stops at the first failure. The three names are
# the committed evidence, so --replace is passed on purpose: running this
# script means "make the committed recordings again".
set -eu
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
python3 -m recorder record normal-1 --experiment normal --replace
python3 -m recorder record normal-2 --experiment normal --replace
python3 -m recorder record e2 --experiment e2 --replace
python3 -m recorder compare recordings/normal-1/recording.json recordings/normal-2/recording.json --out recordings/comparisons/normal-1_vs_normal-2.json
python3 -m recorder compare recordings/normal-1/recording.json recordings/e2/recording.json --out recordings/comparisons/normal-1_vs_e2.json
bash scripts/check-clean.sh
