"""Minimal durable succession journal used by restart conformance tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path


class InjectedCrash(RuntimeError):
    pass


class RecoveryRuntime:
    PHASES = ("OPEN", "FENCED", "COMMITTED", "VERIFIED")

    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS succession (id TEXT PRIMARY KEY, phase TEXT, owner TEXT, epoch INTEGER, obligation_status TEXT)"
        )
        self.connection.commit()

    def initialize(self, succession_id: str) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO succession VALUES (?,?,?,?,?)",
            (succession_id, "OPEN", "v17", 41, "AT_RISK"),
        )
        self.connection.commit()

    def state(self, succession_id: str) -> tuple[str, str, int, str]:
        row = self.connection.execute(
            "SELECT phase,owner,epoch,obligation_status FROM succession WHERE id=?", (succession_id,)
        ).fetchone()
        if not row:
            raise ValueError("SUCCESSION_NOT_FOUND")
        return row

    def resume(self, succession_id: str, fault_after: str | None = None) -> tuple[str, str, int, str]:
        transitions = {
            "OPEN": ("FENCED", "v17", 42, "TRANSFERRING"),
            "FENCED": ("COMMITTED", "v18", 42, "EXECUTING"),
            "COMMITTED": ("VERIFIED", "v18", 42, "DISCHARGED"),
        }
        while self.state(succession_id)[0] != "VERIFIED":
            phase = self.state(succession_id)[0]
            target = transitions[phase]
            with self.connection:
                cursor = self.connection.execute(
                    "UPDATE succession SET phase=?,owner=?,epoch=?,obligation_status=? WHERE id=? AND phase=?",
                    (*target, succession_id, phase),
                )
                if cursor.rowcount != 1:
                    raise ValueError("SUCCESSION_CAS_CONFLICT")
            if fault_after == target[0]:
                raise InjectedCrash(target[0])
        return self.state(succession_id)

    def close(self) -> None:
        self.connection.close()
