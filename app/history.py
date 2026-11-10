import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

DEFAULT_HISTORY_PATH = Path(__file__).resolve().with_name("name_history.json")
MAX_HISTORY_NAMES = 10


class HistoryError(RuntimeError):
    """Raised when the persistent generated-name history cannot be used."""


def load_recent_names(path: Path = DEFAULT_HISTORY_PATH) -> list[str]:
    """Load the most recent names, returning an empty list when no file exists."""
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise HistoryError(
            f"Unable to read name history from '{path}': {exc}"
        ) from exc

    try:
        names = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HistoryError(
            f"Name history at '{path}' is not valid JSON: {exc}"
        ) from exc

    if not isinstance(names, list) or not all(
        isinstance(name, str) and name.strip() for name in names
    ):
        raise HistoryError(
            f"Name history at '{path}' must be a JSON list of non-empty strings."
        )

    return names[-MAX_HISTORY_NAMES:]


def record_name(name: str, path: Path = DEFAULT_HISTORY_PATH) -> None:
    """Append one generated name and atomically retain only the latest 10."""
    _write_names((name,), path, retain_batch=False)


def record_names(names: Sequence[str], path: Path = DEFAULT_HISTORY_PATH) -> None:
    """Append a family batch atomically, retaining every name from that batch."""
    _write_names(names, path, retain_batch=True)


def _write_names(
    names: Sequence[str],
    path: Path,
    *,
    retain_batch: bool,
) -> None:
    if isinstance(names, (str, bytes)) or not names:
        raise ValueError("names must be a non-empty sequence of names.")
    if not all(isinstance(name, str) and name.strip() for name in names):
        raise ValueError("Every name must be a non-empty string.")

    retained_names = [
        *load_recent_names(path)[-MAX_HISTORY_NAMES:],
        *(name.strip() for name in names),
    ]
    if not retain_batch:
        retained_names = retained_names[-MAX_HISTORY_NAMES:]
    temporary_path: Path | None = None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as history_file:
            temporary_path = Path(history_file.name)
            json.dump(retained_names, history_file, ensure_ascii=False, indent=2)
            history_file.write("\n")
            history_file.flush()
            os.fsync(history_file.fileno())

        os.replace(temporary_path, path)
    except OSError as exc:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as cleanup_exc:
                raise HistoryError(
                    f"Unable to write name history to '{path}' and could not "
                    f"remove temporary file '{temporary_path}': {cleanup_exc}"
                ) from cleanup_exc
        raise HistoryError(f"Unable to write name history to '{path}': {exc}") from exc
