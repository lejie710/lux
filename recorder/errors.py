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
    """A program the recorder needs is not installed, or it failed."""


class KeysRefused(LuxError):
    """The committed test keys are missing, changed, or would be overwritten."""


class FormatError(LuxError):
    """A file or byte string does not have the layout the parser expects."""
