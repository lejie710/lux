# Predictions

One file per counted experiment: `<experiment-id>.json`, in the format
described in `docs/DESIGN.md` section 6.

A counted experiment is one that was never run before its prediction was
written. The recorder refuses to run it unless its prediction file is here,
is valid, describes the same change as the experiment in the same words,
and is committed, with the file on disk byte for byte equal to the committed
one. The recording then stores the prediction's hash and commit, so a
prediction edited after its run is detected.

A prediction also carries the values that decide what its experiment tests,
in `parameters`: `signature_area_offset` for `signature-byte`, and
`firmware_sha256` for `rebuilt-firmware`. `boot-order` has none. The
recorder takes these values from the committed prediction and from nowhere
else, so they cannot be chosen after the result is known.

No prediction has been committed yet, so no counted experiment has been run.
