"""Remove what legitimately differs between two identical boots.

Two things would otherwise leak into a recording: the run directory's path
(which contains a machine's folder names) and wall-clock values. Paths are
masked here; wall-clock fields are kept but listed in the recording's
`may_vary` list, which the comparison ignores.

Nothing here sorts anything: event order and console line order carry
meaning and are kept as captured.
"""
RUN_DIRECTORY_MASK = "<run-dir>"
_HOST_PATH_MARKERS = ("/home/", "/root/", "/mnt/", "/Users/", ":\\", "/tmp/")


def mask_run_directory(text: str, run_directory: str) -> str:
    """Replace every occurrence of the run directory's path with a fixed mask."""
    return text.replace(run_directory.rstrip("/"), RUN_DIRECTORY_MASK)


def round_seconds(seconds: float) -> float:
    """Wall-clock durations are kept to one decimal; more would be noise."""
    return round(seconds, 1)


def find_host_paths(value: object, where: str = "") -> list[str]:
    """Dotted locations of every string that still looks like a host path.

    Used as a last check before a recording is written, so that no user name
    or machine folder reaches the repository.
    """
    if isinstance(value, str):
        return [where] if any(marker in value for marker in _HOST_PATH_MARKERS) else []
    if isinstance(value, dict):
        found: list[str] = []
        for key, item in value.items():
            found += find_host_paths(item, f"{where}.{key}" if where else str(key))
        return found
    if isinstance(value, list):
        found = []
        for index, item in enumerate(value):
            found += find_host_paths(item, f"{where}[{index}]")
        return found
    return []
