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
"""
from dataclasses import dataclass

from recorder.errors import StagingRefused

KIND_NORMAL = "normal"
KIND_PILOT = "pilot"
KIND_COUNTED = "counted"

LOADER_SIGNED = "signed"
LOADER_CONTENT_BYTE = "content-byte"
LOADER_SIGNATURE_BYTE = "signature-byte"

EDIT_SECURE_BOOT_OFF = "secure-boot-off"
EDIT_REVERSE_BOOT_ORDER = "reverse-boot-order"
EDIT_REVOKE_LOADER_HASH = "revoke-loader-hash"

FIRMWARE_PACKAGED = "packaged-secure-boot"
FIRMWARE_REBUILT = "rebuilt"


@dataclass(frozen=True)
class Experiment:
    """What one experiment changes, and nothing about how to run it."""

    identifier: str
    kind: str
    change: str                           # one sentence: what was changed
    loader: str = LOADER_SIGNED           # which loader variant goes on the disk
    store_edits: tuple[str, ...] = ()     # edits to the variable store
    firmware: str = FIRMWARE_PACKAGED
    # Offset inside the signature area of the byte to change. It is part of
    # the prediction, so it stays unset until that prediction is written.
    signature_area_offset: int | None = None


EXPERIMENTS: dict[str, Experiment] = {e.identifier: e for e in (
    Experiment("normal", KIND_NORMAL, "none"),
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
    Experiment("boot-order", KIND_COUNTED, "BootOrder lists its entries in reverse",
               store_edits=(EDIT_REVERSE_BOOT_ORDER,)),
    Experiment("signature-byte", KIND_COUNTED,
               "one byte changed inside the loader's signature area, Secure Boot on",
               loader=LOADER_SIGNATURE_BYTE),
    Experiment("rebuilt-firmware", KIND_COUNTED,
               "firmware rebuilt with one driver changed", firmware=FIRMWARE_REBUILT),
)}


def get(identifier: str) -> Experiment:
    """The description for an identifier. Raises `StagingRefused` naming the known ones."""
    if identifier not in EXPERIMENTS:
        raise StagingRefused(
            f"unknown experiment '{identifier}'; known: {', '.join(sorted(EXPERIMENTS))}")
    return EXPERIMENTS[identifier]
