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
in `parameters`: `signature_area_offset` for `signature-byte` and
`signature-byte-off`, and `firmware_sha256` for `rebuilt-firmware`. The boot
order experiments have none. The recorder takes these values from the
committed prediction and from nowhere else, so they cannot be chosen after
the result is known.

## What is here

| File | The one thing changed | Compared with |
|---|---|---|
| `boot-order-same.json` | `BootOrder` lists entry B before entry A; both entries hold the same signed loader | `normal-two-same-1` |
| `boot-order-different.json` | The same change; entry B holds a second signed loader | `normal-two-different-1` |
| `signature-byte.json` | One byte inside the signature value of the loader, Secure Boot on | `normal-1` |
| `signature-byte-off.json` | The same byte, Secure Boot switched off | `normal-1` |

Each file opens with `wrong_if`: what result would prove the prediction
wrong, in plain sentences. Each row names one field of the comparison, what
is expected there, where the expectation comes from (one of four labels),
and a reason. `not_scored` lists what is expected and cannot be checked from
a recording.

**None of these four experiments has been run.** `docs/COUNTED.md` says how
each is staged, what was booted to prepare them (normal runs and preparation
boots only), and how each is to be run, once. A prediction is never edited
after its run; a row that does not hold is reported as a mismatch.

`rebuilt-firmware` has no prediction, so the recorder still refuses it.
