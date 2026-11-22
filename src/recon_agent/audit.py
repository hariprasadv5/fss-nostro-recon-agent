"""Tamper-evident audit trail: append-only JSONL where each record carries the hash of the previous one."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLog:
    def __init__(self, path: Path, run_id: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self._prev = self._last_hash()

    def _last_hash(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return "GENESIS"
        return json.loads(self.path.read_text(encoding="utf-8").strip().splitlines()[-1])["hash"]

    def log(self, actor: str, event: str, **details) -> dict:
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run_id": self.run_id,
               "actor": actor, "event": event, "details": details, "prev_hash": self._prev}
        rec["hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        self._prev = rec["hash"]
        return rec


def verify_chain(path: Path) -> tuple[bool, int]:
    """Recompute every hash; returns (ok, records_checked). Any edit to a past record breaks the chain."""
    prev = "GENESIS"
    lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
    for n, line in enumerate(lines, start=1):
        rec = json.loads(line)
        h = rec.pop("hash")
        if rec["prev_hash"] != prev or hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest() != h:
            return False, n
        prev = h
    return True, len(lines)
