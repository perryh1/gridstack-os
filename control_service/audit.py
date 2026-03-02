"""
Append-only audit log for all dispatch commands sent to hardware.

Uses SQLite for zero-dependency persistence.
"""

import sqlite3
import logging
from datetime import datetime, timezone
from typing import Optional

from .models import DispatchDecision

logger = logging.getLogger(__name__)


class AuditLogger:
    """Logs every dispatch command to a SQLite database."""

    def __init__(self, db_path: str = "audit.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                lmp         REAL,
                gen_mw      REAL,
                mining_mw   REAL,
                bess_charge_mw    REAL,
                bess_discharge_mw REAL,
                bess_soc_mwh      REAL,
                grid_export_mw    REAL,
                grid_import_mw    REAL,
                dispatch_mode     TEXT,
                alerts            TEXT,
                miner_cmd_ok      INTEGER,
                bess_cmd_ok       INTEGER
            )
        """)
        self.conn.commit()

    def record(
        self,
        decision: DispatchDecision,
        lmp: float,
        gen_mw: float,
        bess_soc_mwh: float,
        alerts: list[str],
        miner_cmd_ok: bool,
        bess_cmd_ok: bool,
    ):
        """Record one dispatch cycle to the audit log."""
        try:
            self.conn.execute("""
                INSERT INTO audit_log
                (timestamp, lmp, gen_mw, mining_mw, bess_charge_mw,
                 bess_discharge_mw, bess_soc_mwh, grid_export_mw,
                 grid_import_mw, dispatch_mode, alerts, miner_cmd_ok, bess_cmd_ok)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                lmp,
                gen_mw,
                decision.mining_mw,
                decision.bess_charge_mw,
                decision.bess_discharge_mw,
                bess_soc_mwh,
                decision.grid_export_mw,
                decision.grid_import_mw,
                decision.dispatch_mode,
                "; ".join(alerts) if alerts else "",
                int(miner_cmd_ok),
                int(bess_cmd_ok),
            ))
            self.conn.commit()
        except Exception as e:
            logger.error("Audit log write failed: %s", e)

    def get_recent(self, limit: int = 100) -> list[dict]:
        """Return the most recent audit entries."""
        cursor = self.conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self):
        self.conn.close()
