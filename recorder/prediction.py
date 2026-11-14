"""Prediction files: load them, enforce "committed before the run", score them.

The measure of this project is a prediction written before an experiment is
run. That only means something if the recorder itself refuses to run a
counted experiment without one. This module holds that rule:

* `require_committed` answers "is a valid prediction for this experiment
  committed, and is the file on disk byte for byte the committed one?" and
  raises `PredictionMissing` otherwise. If git cannot answer, the answer is
  no.
* A prediction also carries the experiment's **parameters**: the values that
  decide what the experiment tests (which signature byte, which rebuilt
  firmware). Staging reads them from the committed prediction and from
  nowhere else, so they cannot be chosen after the result is known.
* `score` checks a comparison against the prediction's rows and reports two
  numbers: specification-required rows met, and open rows predicted right.
  `score_document` wraps them as the result file (`lux-score/1`).

Every row carries one of four basis labels saying where the expectation
comes from; `validate` rejects a row whose label and citation do not fit.

A row holds exactly one expectation about one field of the comparison:

* `expect`: the field equals this value;
* `expect_one_of`: the field equals one of these values. This is how a row
  says "either X or Y" where a specification leaves the choice open; every
  allowed value is named before the run;
* `expect_contains` / `expect_excludes`: the field is a list that holds all
  of these, or none of these;
* `expect_text_contains`: the field is a text that contains this text.

A prediction may also carry three things that are not rows:

* `wrong_if`: plain sentences, written before the run, that say what result
  would prove the prediction wrong;
* `not_scored`: expectations that no field of a comparison can show, so that
  they are on record without being counted;
* `baseline`: the name and SHA-256 of the normal recording the rows were
  written against. Row values such as event numbers only mean something
  against that recording, so `check` refuses a comparison made against
  another one (`fits_baseline`).
"""
import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from recorder import experiments
from recorder.errors import FormatError, PredictionMissing
from recorder.experiments import Experiment

PREDICTION_FORMAT = "lux-prediction/1"
SCORE_FORMAT = "lux-score/1"

BASIS_REQUIRED = "uefi-required"
BASIS_PLATFORM = "uefi-platform"
BASIS_TCG_UNREAD = "tcg-unread"
BASIS_THIS_FIRMWARE = "this-firmware"
BASIS_LABELS = (BASIS_REQUIRED, BASIS_PLATFORM, BASIS_TCG_UNREAD, BASIS_THIS_FIRMWARE)

_EXPECTATION_KEYS = ("expect", "expect_one_of", "expect_contains", "expect_excludes",
                     "expect_text_contains")
_LIST_EXPECTATIONS = ("expect_one_of", "expect_contains", "expect_excludes")
_CITATION_KEYS = ("document", "version", "section", "page")

# Runs a git command in a directory; returns (exit code, standard output as bytes).
# Bytes, not text, because one of the answers is the committed file itself.
GitQuery = Callable[[list[str], Path], tuple[int, bytes]]


@dataclass(frozen=True)
class PredictionRef:
    """Which prediction a counted run was made under; stored in its recording."""

    path: str                       # relative to the repository root
    sha256: str                     # of the committed file, equal to the file on disk
    commit: str
    parameters: dict[str, object]   # the experiment's values, from the committed file

    def as_document(self) -> dict[str, object]:
        return {"path": self.path, "sha256": self.sha256, "commit": self.commit,
                "parameters": dict(self.parameters)}


def run_git(arguments: list[str], directory: Path) -> tuple[int, bytes]:
    """The real git query. Any failure to run git is reported as exit code 1."""
    try:
        done = subprocess.run(["git", *arguments], cwd=directory, capture_output=True,
                              timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return 1, b""
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
    for key in _LIST_EXPECTATIONS:
        if key in row and (not isinstance(row[key], list) or not row[key]):
            raise FormatError(f"row '{row_id}': '{key}' must be a list with at least one value")
    if "expect_one_of" in row and len(row["expect_one_of"]) < 2:
        raise FormatError(f"row '{row_id}': 'expect_one_of' names at least two values; "
                          "use 'expect' for one")
    if "expect_text_contains" in row and (not isinstance(row["expect_text_contains"], str)
                                          or not row["expect_text_contains"]):
        raise FormatError(f"row '{row_id}': 'expect_text_contains' must be a text")
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
    for key in ("wrong_if", "not_scored"):
        sentences = document.get(key)
        if sentences is not None and (not isinstance(sentences, list) or not sentences or not all(
                isinstance(sentence, str) and sentence.strip() for sentence in sentences)):
            raise FormatError(f"'{key}' must be a list of sentences")
    baseline = document.get("baseline")
    if baseline is not None and (not isinstance(baseline, dict)
                                 or not str(baseline.get("run", "")).strip()
                                 or not _is_sha256(baseline.get("recording_sha256"))):
        raise FormatError("'baseline' must name a run and its recording's SHA-256")
    _validate_parameters(document.get("parameters", {}))
    return document


def _is_sha256(value: object) -> bool:
    """True for 64 lowercase hexadecimal digits."""
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def fits_baseline(document: dict[str, object], comparison: dict[str, object]) -> bool:
    """True when a comparison was made against the recording the prediction names.

    A prediction without a `baseline` fits any comparison.
    """
    baseline = document.get("baseline")
    if not isinstance(baseline, dict):
        return True
    return baseline.get("recording_sha256") == comparison.get("baseline", {}).get("recording_sha256")


def _validate_parameters(parameters: object) -> None:
    """Parameters are optional; when present, each known one must have its type."""
    if not isinstance(parameters, dict):
        raise FormatError("'parameters' must be an object")
    offset = parameters.get(experiments.PARAMETER_SIGNATURE_OFFSET)
    if offset is not None and (not isinstance(offset, int) or isinstance(offset, bool) or offset < 0):
        raise FormatError(f"'{experiments.PARAMETER_SIGNATURE_OFFSET}' must be a whole number from 0")
    digest = parameters.get(experiments.PARAMETER_FIRMWARE_SHA256)
    if digest is not None and not _is_sha256(digest):
        raise FormatError(f"'{experiments.PARAMETER_FIRMWARE_SHA256}' must be 64 lowercase hex digits")


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


def _require_fits_experiment(document: dict[str, object], experiment: Experiment,
                             refusal: str) -> dict[str, object]:
    """The prediction must be about this experiment, in every respect; return its parameters.

    Same identifier, the same one-sentence change, and exactly the
    parameters the experiment needs. A prediction that describes another
    change than the code makes would be a prediction of something else.
    """
    if document["experiment"] != experiment.identifier:
        raise PredictionMissing(refusal + "its prediction file names another experiment")
    if document["change"] != experiment.change:
        raise PredictionMissing(
            refusal + "its prediction describes another change than the experiment makes "
            f"(prediction: '{document['change']}'; experiment: '{experiment.change}')")
    parameters = document.get("parameters", {})
    if set(parameters) != set(experiment.parameters):
        needed = ", ".join(experiment.parameters) or "none"
        raise PredictionMissing(
            refusal + f"its prediction must carry exactly these parameters: {needed}")
    return dict(parameters)


def _committed_bytes(path: Path, refusal: str, git: GitQuery) -> tuple[bytes, str, str]:
    """The committed content of a file, the commit that holds it, and its repository path.

    All of these must hold: git tracks the file, git sees no uncommitted
    change, git can name the commit that last changed it, that commit is
    part of the current history, and git can hand out the committed bytes.
    """
    directory, name = path.parent, path.name
    tracked, _ = git(["ls-files", "--error-unmatch", "--", name], directory)
    if tracked != 0:
        raise PredictionMissing(refusal + "its prediction is not committed (git does not track it)")
    status_code, status = git(["status", "--porcelain", "--", name], directory)
    if status_code != 0 or status.strip():
        raise PredictionMissing(refusal + "its prediction has changes that are not committed")
    log_code, log = git(["log", "-n", "1", "--format=%H", "--", name], directory)
    commit = log.decode("ascii", errors="replace").strip()
    if log_code != 0 or not commit:
        raise PredictionMissing(refusal + "git cannot name the commit that holds its prediction")
    ancestor, _ = git(["merge-base", "--is-ancestor", commit, "HEAD"], directory)
    if ancestor != 0:
        raise PredictionMissing(refusal + "the commit that holds its prediction is not part "
                                "of the current history")
    prefix_code, prefix = git(["rev-parse", "--show-prefix"], directory)
    if prefix_code != 0:
        raise PredictionMissing(refusal + "git cannot say where its prediction lies in the repository")
    repository_path = prefix.decode("utf-8", errors="replace").strip() + name
    blob_code, blob = git(["cat-file", "blob", f"{commit}:{repository_path}"], directory)
    if blob_code != 0:
        raise PredictionMissing(refusal + "git cannot read the committed prediction")
    return blob, commit, repository_path


def require_committed(experiment: Experiment, predictions_directory: Path,
                      git: GitQuery = run_git) -> PredictionRef:
    """Return a reference to the committed prediction, or raise `PredictionMissing`.

    The file must exist, validate and fit the experiment, and the bytes on
    disk must be exactly the bytes git has committed. The last point is
    checked by reading the committed file out of git and comparing hashes;
    git's own "nothing changed" answer is not trusted alone, because git can
    be told to stop looking at a file.
    """
    path = prediction_path(predictions_directory, experiment.identifier)
    refusal = f"experiment '{experiment.identifier}' is counted and must not run: "
    if not path.is_file():
        raise PredictionMissing(refusal + f"no prediction file {path.name} exists")
    try:
        document = load(path)
    except FormatError as error:
        raise PredictionMissing(refusal + f"its prediction is not valid ({error})") from error
    parameters = _require_fits_experiment(document, experiment, refusal)

    committed, commit, repository_path = _committed_bytes(path, refusal, git)
    digest = hashlib.sha256(committed).hexdigest()
    if digest != hashlib.sha256(path.read_bytes()).hexdigest():
        raise PredictionMissing(refusal + "its prediction file differs from the committed one")
    return PredictionRef(repository_path, digest, commit, parameters)


def unchanged_since_run(recording: dict[str, object], prediction_file: Path) -> bool:
    """True when the prediction file still has the hash stored in the recording."""
    stored = recording.get("provenance", {}).get("prediction")
    if not isinstance(stored, dict) or not prediction_file.is_file():
        return False
    return stored.get("sha256") == hashlib.sha256(prediction_file.read_bytes()).hexdigest()


# ---------------------------------------------------------------- scoring

def lookup(document: dict[str, object], dotted_path: str) -> object:
    """Follow a dotted path into a comparison document. Raises `FormatError` if absent.

    A block of the comparison can be null (no event differs, for example).
    A path into such a block gives null and no error, so a row that expected
    a value there is reported as a mismatch and the score is still made.
    """
    value: object = document
    for part in dotted_path.split("."):
        if value is None:
            return None         # a block that is null has no parts; the row then sees null
        if not isinstance(value, dict) or part not in value:
            raise FormatError(f"the comparison has no field '{dotted_path}'")
        value = value[part]
    return value


def row_holds(row: dict[str, object], comparison: dict[str, object]) -> bool:
    """True when the comparison shows what the row expected."""
    actual = lookup(comparison, str(row["field"]))
    if "expect" in row:
        return actual == row["expect"]
    if "expect_one_of" in row:
        return any(actual == allowed for allowed in row["expect_one_of"])
    if "expect_text_contains" in row:
        if not isinstance(actual, str):
            return False        # for example no differing line at all, where one was expected
        return row["expect_text_contains"] in actual
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


def score_document(result: dict[str, object], sources: dict[str, object]) -> dict[str, object]:
    """The score as a file the site can load: the numbers, the rows, and what they rest on.

    `sources` names the run, the prediction it was recorded under, and the
    hashes of the comparison and the recordings the score was computed
    from, so a reader can check that the numbers belong to those files.
    """
    return {"format": SCORE_FORMAT, **sources, **result}
