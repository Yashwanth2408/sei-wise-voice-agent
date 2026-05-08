from __future__ import annotations


import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4



class CallTelemetry:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.call_id = uuid4().hex
        self._path = directory / f"call_{self.call_id}.jsonl"


    def log(self, event: str, **fields) -> None:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "call_id": self.call_id,
            "event": event,
            **fields,
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True))
            handle.write("\\n")


    @property
    def path(self) -> Path:
        return self._path
