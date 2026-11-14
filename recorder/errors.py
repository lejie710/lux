"""The small family of errors the recorder raises on purpose.

Every command catches `LuxError` at the top, prints one plain sentence and
exits with a non-zero code. Callers never need to catch a bare `Exception`.
"""


class LuxError(Exception):
    """Base class: something the recorder refuses to do or cannot trust."""


class GateFailure(LuxError):
    """The readings of one boot disagree, so no recording may be written."""


class PredictionMissing(LuxError):
    """A counted experiment was asked for without a committed prediction."""


class StagingRefused(LuxError):
    """A run could not be prepared the way its description demands."""


class ToolMissing(LuxError):
    """A program the recorder needs is not installed, or a command it ran failed."""


class MachineFailure(LuxError):
    """The virtual machine or the software TPM did not do what a run needs.

    Examples: QEMU ended before the guest printed anything, the guest did not
    pause, the TPM did not return all its registers, a process survived the
    cleanup. The tools are installed; this boot cannot be trusted.
    """


class RunIncomplete(LuxError):
    """A boot ended in a way its experiment does not allow, so it is not recorded.

    Examples: a normal run that was not accepted, or a boot that never became
    quiet before it was paused.
    """


class RecordingExists(LuxError):
    """A recording of that name already exists and may not be overwritten."""


class ComparisonRefused(LuxError):
    """Two recordings may not be compared, or a comparison may not be scored."""


class KeysRefused(LuxError):
    """The committed test keys are missing, changed, or would be overwritten."""


class FormatError(LuxError):
    """A file or byte string does not have the layout the parser expects."""
