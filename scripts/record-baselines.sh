#!/usr/bin/env bash
# Record the normal runs of the boot order experiments: two boot entries in
# the original order (A, then B), each form twice, and compare each pair.
# These are normal runs and need no prediction. The four names are committed
# evidence, so --replace is passed on purpose: running this script means
# "make these recordings again". The changed order is never staged here.
set -eu
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
for form in same different; do
  python3 -m recorder record "normal-two-$form-1" --experiment "normal-two-$form" --replace
  python3 -m recorder record "normal-two-$form-2" --experiment "normal-two-$form" --replace
  python3 -m recorder compare "recordings/normal-two-$form-1/recording.json" "recordings/normal-two-$form-2/recording.json" --out "recordings/comparisons/normal-two-$form-1_vs_normal-two-$form-2.json"
done
bash scripts/check-clean.sh
