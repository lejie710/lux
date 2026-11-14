"""Prediction files: load them, enforce "committed before the run", score them.

The measure of this project is a prediction written before an experiment is
run. That only means something if the recorder itself refuses to run a
counted experiment without one. This module holds that rule:

* `require_committed` answers "is a valid prediction for this experiment
  tracked by git, with no uncommitted change?" and raises
  `PredictionMissing` otherwise. If git cannot answer, the answer is no.
* `score` checks a comparison against the prediction's rows and reports two
  numbers: specification-required rows met, and open rows predicted right.

Every row carries one of four basis labels saying where the expectation
comes from; `validate` rejects a row whose label and citation do not fit.
"""
import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from recorder.errors import FormatError, PredictionMissing

PREDICTION_FORMAT = "lux-prediction/1"

BASIS_REQUIRED = "uefi-required"
BASIS_PLATFORM = "uefi-platform"
BASIS_TCG_UNREAD = "tcg-unread"
BASIS_THIS_FIRMWARE = "this-firmware"
BASIS_LABELS = (BASIS_REQUIRED, BASIS_PLATFORM, BASIS_TCG_UNREAD, BASIS_THIS_FIRMWARE)

_EXPECTATION_KEYS = ("expect", "expect_contains", "expect_excludes")
_CITATION_KEYS = ("document", "version", "section", "page")

# Runs a git command in a directory; returns (exit code, standard output).
GitQuery = Callable[[list[str], Path], tuple[int, str]]


@dataclass(frozen=True)
class PredictionRef:
    """Which prediction a counted run was made under; stored in its recording."""

    path: str
    sha256: str
    commit: str

    def as_document(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256, "commit": self.commit}


def run_git(arguments: list[str], directory: Path) -> tuple[int, str]:
    """The real git query. Any failure to run git is reported as exit code 1."""
    try:
        done = subprocess.run(["git", *arguments], cwd=directory, capture_output=True,
                              text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return done.returncode, done.stdout


# ---------------------------------------------------------------- validation

def _validate_citation(row_id: str, citation: object) -> None:
    if not isinstance(citation, dict):
        raise FormatError(f"row '{row_id}': this basis needs a citation")
    for key in _CITATION_KEYS:
        if key not in citation:
            raise FormatError(f"row '{row_id}': the citation has no '{key}'")
    if not isinstance(citation["page"], int) or not str(citation["section"]).strip():
        raise FormatError(f"row '{row_id}': the citation needs a section title and a page number")


def _validate_row(row: object) -> None:
    """Check one row: an identifier, a field, one expectation, a fitting basis."""
    if not isinstance(row, dict) or not str(row.get("id", "")).strip():
        raise FormatError("every row needs an 'id'")
    row_id = str(row["id"])
    if not str(row.get("field", "")).strip():
        raise FormatError(f"row '{row_id}': 'field' is missing")
    if sum(key in row for key in _EXPECTATION_KEYS) != 1:
        raise FormatError(f"row '{row_id}': exactly one of {_EXPECTATION_KEYS} is needed")
    basis = row.get("basis")
    if basis not in BASIS_LABELS:
        raise FormatError(f"row '{row_id}': unknown basis '{basis}'")
    if basis in (BASIS_REQUIRED, BASIS_PLATFORM):
        _validate_citation(row_id, row.get("citation"))
    elif row.get("citation") is not None:
        raise FormatError(f"row '{row_id}': basis '{basis}' must not carry a citation")
    if basis == BASIS_TCG_UNREAD and not str(row.get("reason", "")).strip():
        raise FormatError(f"row '{row_id}': an unread document needs a 'reason' instead")
    if basis == BASIS_THIS_FIRMWARE and not str(row.get("source", "")).strip():
        raise FormatError(f"row '{row_id}': name a source file or an earlier recording in 'source'")


def validate(document: object) -> dict[str, object]:
    """Check a prediction document; return it, or raise `FormatError`."""
    if not isinstance(document, dict) or document.get("format") != PREDICTION_FORMAT:
        raise FormatError(f"not a '{PREDICTION_FORMAT}' document")
    for key in ("experiment", "written", "change"):
        if not str(document.get(key, "")).strip():
            raise FormatError(f"the prediction has no '{key}'")
    rows = document.get("rows")
    if not isinstance(rows, list) or not rows:
        raise FormatError("the prediction has no rows")
    for row in rows:
        _validate_row(row)
    identifiers = [row["id"] for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise FormatError("two rows share one 'id'")
    return document


def load(path: Path) -> dict[str, object]:
    """Read and validate a prediction file."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise FormatError(f"cannot read prediction {path.name}: {error}") from error
    return validate(document)


# ---------------------------------------------------------------- the gate

def prediction_path(predictions_directory: Path, experiment: str) -> Path:
    """Where the prediction for an experiment must live."""
    return predictions_directory / f"{experiment}.json"


def require_committed(experiment: str, predictions_directory: Path,
                      git: GitQuery = run_git) -> PredictionRef:
    """Return a reference to the committed prediction, or raise `PredictionMissing`.

    All of these must hold: the file exists, it validates, it names this
    experiment, git tracks it, it has no uncommitted change, and git can
    name the commit that last changed it.
    """
    path = prediction_path(predictions_directory, experiment)
    refusal = f"experiment '{experiment}' is counted and must not run: "
    if not path.is_file():
        raise PredictionMissing(refusal + f"no prediction file {path.name} exists")
    try:
        document = load(path)
    except FormatError as error:
        raise PredictionMissing(refusal + f"its prediction is not valid ({error})") from error
    if document["experiment"] != experiment:
        raise PredictionMissing(refusal + "its prediction file names another experiment")

    directory = path.parent
    tracked, _ = git(["ls-files", "--error-unmatch", "--", path.name], directory)
    if tracked != 0:
        raise PredictionMissing(refusal + "its prediction is not committed (git does not track it)")
    status_code, status = git(["status", "--porcelain", "--", path.name], directory)
    if status_code != 0 or status.strip():
        raise PredictionMissing(refusal + "its prediction has changes that are not committed")
    log_code, commit = git(["log", "-n", "1", "--format=%H", "--", path.name], directory)
    if log_code != 0 or not commit.strip():
        raise PredictionMissing(refusal + "git cannot name the commit that holds its prediction")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return PredictionRef(f"predictions/{path.name}", digest, commit.strip())


def unchanged_since_run(recording: dict[str, object], prediction_file: Path) -> bool:
    """True when the prediction file still has the hash stored in the recording."""
    stored = recording.get("provenance", {}).get("prediction")
    if not isinstance(stored, dict) or not prediction_file.is_file():
        return False
    return stored.get("sha256") == hashlib.sha256(prediction_file.read_bytes()).hexdigest()


# ---------------------------------------------------------------- scoring

def lookup(document: dict[str, object], dotted_path: str) -> object:
    """Follow a dotted path into a comparison document. Raises `FormatError` if absent."""
    value: object = document
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise FormatError(f"the comparison has no field '{dotted_path}'")
        value = value[part]
    return value


def row_holds(row: dict[str, object], comparison: dict[str, object]) -> bool:
    """True when the comparison shows what the row expected."""
    actual = lookup(comparison, str(row["field"]))
    if "expect" in row:
        return actual == row["expect"]
    if not isinstance(actual, list):
        raise FormatError(f"row '{row['id']}': field '{row['field']}' is not a list")
    if "expect_contains" in row:
        return all(item in actual for item in row["expect_contains"])
    return all(item not in actual for item in row["expect_excludes"])


def score(prediction: dict[str, object], comparison: dict[str, object]) -> dict[str, object]:
    """Score a comparison against a prediction.

    The result is the project's two numbers: how many specification-required
    rows were met, and how many open rows (the other three labels) were
    predicted correctly. Every mismatch is listed; none is hidden.
    """
    rows = []
    for row in prediction["rows"]:
        rows.append({"id": row["id"], "basis": row["basis"], "held": row_holds(row, comparison)})
    required = [row for row in rows if row["basis"] == BASIS_REQUIRED]
    open_rows = [row for row in rows if row["basis"] != BASIS_REQUIRED]
    return {
        "experiment": prediction["experiment"],
        "required_met": sum(row["held"] for row in required),
        "required_total": len(required),
        "open_correct": sum(row["held"] for row in open_rows),
        "open_total": len(open_rows),
        "mismatches": [row["id"] for row in rows if not row["held"]],
        "rows": rows,
    }
