"""The experiments, each written down as data.

An experiment changes exactly one thing compared with the normal run. Each
is a small frozen description; adding an experiment means adding a
description here, not a new code path.

Kinds:

* `normal`: the unchanged boot. Two of these must match before anything else
  counts.
* `pilot`: a changed boot that was first run before any prediction existed.
  It is shown as a pilot and never counted.
* `counted`: a changed boot that must not run until its prediction is
  committed. The recorder enforces that (see `prediction.require_committed`).

Some experiments need a value that decides what they test: which byte of the
signature area is changed, or which rebuilt firmware file is booted. Such a
value is never written here. It is a **parameter** of the committed
prediction, so it is fixed by the same commit as the prediction itself and
cannot be chosen after the result is known.

Every changed run is compared with one normal run, its `baseline`. Most
experiments change the plain normal run. The boot order experiments need a
machine with two boot entries, so they have normal runs of their own
(`normal-two-same`, `normal-two-different`): the same two entries in the
original order. A changed run and its baseline always start from stores
that differ in the one thing the experiment changes.
"""
import hashlib
import json
from dataclasses import asdict, dataclass

from recorder.errors import StagingRefused

KIND_NORMAL = "normal"
KIND_PILOT = "pilot"
KIND_COUNTED = "counted"

LOADER_SIGNED = "signed"
LOADER_CONTENT_BYTE = "content-byte"
LOADER_SIGNATURE_BYTE = "signature-byte"
# A second loader, built with another start message and signed with the same
# key. It only ever sits behind boot entry B.
LOADER_SECOND = "second-signed"
NO_SECOND_ENTRY = ""

EDIT_SECURE_BOOT_OFF = "secure-boot-off"
EDIT_REVOKE_LOADER_HASH = "revoke-loader-hash"

# Which variable store template a run starts from.
STORE_ONE_ENTRY = "one-entry"                 # the firmware's own boot options only
STORE_TWO_ENTRIES = "two-entries"             # entries A and B added, order A then B
STORE_TWO_ENTRIES_B_FIRST = "two-entries-b-first"   # the same, order B then A
TWO_ENTRY_STORES = (STORE_TWO_ENTRIES, STORE_TWO_ENTRIES_B_FIRST)

NORMAL = "normal"

FIRMWARE_PACKAGED = "packaged-secure-boot"
FIRMWARE_REBUILT = "rebuilt"

# Names of the values a prediction file must carry in its `parameters`.
PARAMETER_SIGNATURE_OFFSET = "signature_area_offset"   # a whole number
PARAMETER_FIRMWARE_SHA256 = "firmware_sha256"          # 64 lowercase hex digits


@dataclass(frozen=True)
class Experiment:
    """What one experiment changes, and nothing about how to run it."""

    identifier: str
    kind: str
    change: str                           # one sentence: what was changed
    loader: str = LOADER_SIGNED           # which loader variant goes on the disk
    store_edits: tuple[str, ...] = ()     # edits to the variable store
    firmware: str = FIRMWARE_PACKAGED
    # Parameter names the committed prediction must carry, no more and no fewer.
    parameters: tuple[str, ...] = ()
    store: str = STORE_ONE_ENTRY          # which variable store template the run starts from
    loader_b: str = NO_SECOND_ENTRY       # with two entries: the loader behind entry B
    baseline: str = NORMAL                # the normal run a changed run is compared with


# Fields added after the first recordings were made, with the value each has
# when an experiment does not use it. `fingerprint` leaves such a field out,
# so the fingerprint stored in those recordings still equals the one computed
# from the code.
_LATER_FIELDS: dict[str, str] = {"store": STORE_ONE_ENTRY, "loader_b": NO_SECOND_ENTRY,
                                 "baseline": NORMAL}

_BOOT_ORDER_CHANGE = "BootOrder lists entry B before entry A, written in a preparation boot; "

EXPERIMENTS: dict[str, Experiment] = {e.identifier: e for e in (
    Experiment(NORMAL, KIND_NORMAL, "none"),
    Experiment("normal-two-same", KIND_NORMAL, "none",
               store=STORE_TWO_ENTRIES, loader_b=LOADER_SIGNED),
    Experiment("normal-two-different", KIND_NORMAL, "none",
               store=STORE_TWO_ENTRIES, loader_b=LOADER_SECOND),
    Experiment("e1", KIND_PILOT,
               "one byte of the loader's content changed, Secure Boot switched off",
               loader=LOADER_CONTENT_BYTE, store_edits=(EDIT_SECURE_BOOT_OFF,)),
    Experiment("e2", KIND_PILOT,
               "one byte of the loader's content changed, Secure Boot on",
               loader=LOADER_CONTENT_BYTE),
    Experiment("e4", KIND_PILOT, "Secure Boot switched off, nothing else changed",
               store_edits=(EDIT_SECURE_BOOT_OFF,)),
    Experiment("e5", KIND_PILOT,
               "the signed loader's hash added to the revocation list (dbx)",
               store_edits=(EDIT_REVOKE_LOADER_HASH,)),
    Experiment("boot-order-same", KIND_COUNTED,
               _BOOT_ORDER_CHANGE + "both entries hold the same signed loader",
               store=STORE_TWO_ENTRIES_B_FIRST, loader_b=LOADER_SIGNED,
               baseline="normal-two-same"),
    Experiment("boot-order-different", KIND_COUNTED,
               _BOOT_ORDER_CHANGE + "entry B holds a second signed loader",
               store=STORE_TWO_ENTRIES_B_FIRST, loader_b=LOADER_SECOND,
               baseline="normal-two-different"),
    Experiment("signature-byte", KIND_COUNTED,
               "one byte changed inside the loader's signature area, Secure Boot on",
               loader=LOADER_SIGNATURE_BYTE, parameters=(PARAMETER_SIGNATURE_OFFSET,)),
    Experiment("signature-byte-off", KIND_COUNTED,
               "one byte changed inside the loader's signature area, Secure Boot switched off",
               loader=LOADER_SIGNATURE_BYTE, store_edits=(EDIT_SECURE_BOOT_OFF,),
               parameters=(PARAMETER_SIGNATURE_OFFSET,)),
    Experiment("rebuilt-firmware", KIND_COUNTED,
               "firmware rebuilt with one driver changed", firmware=FIRMWARE_REBUILT,
               parameters=(PARAMETER_FIRMWARE_SHA256,)),
)}


def get(identifier: str) -> Experiment:
    """The description for an identifier. Raises `StagingRefused` naming the known ones."""
    if identifier not in EXPERIMENTS:
        raise StagingRefused(
            f"unknown experiment '{identifier}'; known: {', '.join(sorted(EXPERIMENTS))}")
    return EXPERIMENTS[identifier]


def fingerprint(experiment: Experiment) -> str:
    """SHA-256 of an experiment's description, stored in every recording.

    If a description is edited after a run, the stored value no longer
    equals the one computed from the code, and `check` says so. A field
    listed in `_LATER_FIELDS` is part of the fingerprint only when the
    experiment uses it.
    """
    description = {name: value for name, value in asdict(experiment).items()
                   if not (name in _LATER_FIELDS and _LATER_FIELDS[name] == value)}
    text = json.dumps(description, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def baseline_of(experiment: Experiment) -> Experiment:
    """The normal run an experiment's recording is compared with."""
    baseline = get(experiment.baseline)
    if baseline.kind != KIND_NORMAL:
        raise StagingRefused(f"the baseline of '{experiment.identifier}' is not a normal run")
    return baseline
