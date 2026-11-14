# Predictions

One file per counted experiment: `<experiment-id>.json`, in the format
described in `docs/DESIGN.md` section 6.

A counted experiment is one that was never run before its prediction was
written. The recorder refuses to run it unless its prediction file is here,
is valid, and is committed without later changes. The recording then stores
the prediction's hash and commit, so a prediction edited after its run is
detected.

No prediction has been committed yet, so no counted experiment has been run.
