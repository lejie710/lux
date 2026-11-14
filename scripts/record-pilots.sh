#!/usr/bin/env bash
# Record the runs that are allowed without a prediction: the normal run twice
# and the four declared pilots (e1, e2, e4, e5; docs/PILOTS.md says what each
# changes). Then compare them. Stops at the first failure. The six names are
# the committed evidence, so --replace is passed on purpose: running this
# script means "make the committed recordings again".
set -eu
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
python3 -m recorder record normal-1 --experiment normal --replace
python3 -m recorder record normal-2 --experiment normal --replace
for pilot in e1 e2 e4 e5; do
  python3 -m recorder record "$pilot" --experiment "$pilot" --replace
done
python3 -m recorder compare recordings/normal-1/recording.json recordings/normal-2/recording.json --out recordings/comparisons/normal-1_vs_normal-2.json
for pilot in e1 e2 e4 e5; do
  python3 -m recorder compare recordings/normal-1/recording.json "recordings/$pilot/recording.json" --out "recordings/comparisons/normal-1_vs_$pilot.json"
done
bash scripts/check-clean.sh
