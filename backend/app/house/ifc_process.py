"""IFC im Kindprozess lesen (docs/PLAN_HAUSMODELL.md 3.6, E-HM-19).

Der Job startet `python -m app.house.ifc_process <bytes> <datei>`. Das Kind setzt zuerst die Grenze des
Adressraums und lädt erst danach IfcOpenShell (`app.house.ifc_reader`); die Zeitgrenze hält der Elternprozess.
Ein Absturz oder Speichermangel beendet nur das Kind, der Job meldet einen Code. Kein `preexec_fn`: Der
Worker hat Threads (Sentry), und `fork` mit Python-Code vor `exec` ist dann nicht sicher.
"""

import json
import os
import resource
import subprocess
import sys
from pathlib import Path

from pydantic import ValidationError

from app.house.domain.raw import RawModel

EXIT_UNREADABLE = 3
"""Rückgabewert des Lesers, wenn sich die Datei nicht öffnen lässt; stdout trägt dann `{"error": …}`."""
APP_ROOT = Path(__file__).resolve().parents[2]
READ_ERRORS = ("file_unreadable", "schema_unsupported", "reader_timeout", "reader_limit", "reader_failed")
MEMORY_MARKERS = ("MemoryError", "bad_alloc", "Memory allocation", "Cannot allocate memory")


class IfcReadError(Exception):
    """Datei nicht gelesen; `code` ist einer aus `READ_ERRORS` und geht als Fehler in den Importbericht."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def read_ifc(path: Path, *, timeout_seconds: float, max_memory_bytes: int) -> RawModel:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(APP_ROOT),
        "LANG": "C.UTF-8",
        # OpenBLAS (über numpy) reserviert je Thread Puffer im Adressraum (Spike HM0)
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
    }
    try:
        done = subprocess.run(  # noqa: S603  feste Argumente: dieses Modul und ein Pfad im Dateiverzeichnis
            [sys.executable, "-m", "app.house.ifc_process", str(max_memory_bytes), str(path)],
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            cwd=APP_ROOT,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise IfcReadError("reader_timeout", f"{timeout_seconds:g} s") from exc
    if done.returncode == EXIT_UNREADABLE:
        try:
            reported = json.loads(done.stdout)
            raise IfcReadError(str(reported["error"]), str(reported.get("detail", ""))[:300])
        except (ValueError, KeyError, TypeError):
            raise IfcReadError("file_unreadable") from None
    if done.returncode != 0:
        stderr = done.stderr.decode("utf-8", errors="replace").strip()
        last = stderr.splitlines()[-1][:300] if stderr else f"Rückgabewert {done.returncode}"
        # Speichergrenze: MemoryError in Python, Meldung von OpenBLAS, std::bad_alloc (Abbruch per Signal)
        limit = done.returncode < 0 or any(marker in stderr for marker in MEMORY_MARKERS)
        raise IfcReadError("reader_limit" if limit else "reader_failed", last)
    try:
        return RawModel.model_validate_json(done.stdout)
    except ValidationError as exc:
        raise IfcReadError("reader_failed", str(exc)[:300]) from exc


def _child(argv: list[str]) -> int:
    memory = int(argv[1])
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    from app.house import ifc_reader  # erst nach der Grenze: IfcOpenShell, numpy und Shapely

    return ifc_reader.main([argv[0], argv[2]])


if __name__ == "__main__":
    sys.exit(_child(sys.argv))
