from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType


class JsonlWriter:
    """Streams one JSON object per line so large entity groups never need to be
    held fully in memory before being written out."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle = None

    def __enter__(self) -> "JsonlWriter":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n" pins LF regardless of host OS, required for the --verify
        # reproducibility check's byte-for-byte diff to be meaningful on Windows too.
        self._handle = self._path.open("w", encoding="utf-8", newline="\n")
        return self

    def write(self, record: dict) -> None:
        assert self._handle is not None
        json.dump(record, self._handle, sort_keys=True, default=str)
        self._handle.write("\n")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._handle:
            self._handle.close()
