"""Local multi-site monitor: validated site reports stored in SQLite.

Not a public SaaS/cloud: host only on localhost behind a separately
authenticated and TLS-protected remote access gateway when required.
No site credentials, raw meter keys or controller write actions.
"""
from __future__ import annotations
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from .core import number, utc_time

SITE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$")
STATUS = frozenset(("ok", "warning", "critical", "offline", "unknown"))


def validate_site_report(report):
    if not isinstance(report, dict):
        raise ValueError("Site report must be an object")
    site_id = report.get("site_id")
    if not isinstance(site_id, str) or not SITE_RE.fullmatch(site_id):
        raise ValueError("Invalid site_id")
    stamp = utc_time(report.get("observed_at"))
    name = report.get("name", site_id)
    if not isinstance(name, str) or len(name) > 120:
        raise ValueError("Invalid site name")
    status = report.get("status")
    if status not in STATUS:
        raise ValueError("Invalid site status")
    metrics = report.get("metrics", {})
    if not isinstance(metrics, dict) or len(metrics) > 40:
        raise ValueError("Up to 40 numerical metrics allowed")
    safe_metrics = {}
    for key, value in metrics.items():
        if (not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key)):
            raise ValueError("Unsafe metric key")
        safe_metrics[key] = number(value, key, minimum=-1e9, maximum=1e9)
    alarms = report.get("alarm_codes", [])
    if (not isinstance(alarms, list) or len(alarms) > 30
            or any(not isinstance(s, str)
                   or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", s) for s in alarms)):
        raise ValueError("Invalid alarm codes")
    return {
        "site_id": site_id, "name": name, "observed_at": stamp.isoformat(),
        "status": status, "metrics": safe_metrics, "alarm_codes": alarms,
        "device_commands_issued": 0,
    }


class SiteStore:
    def __init__(self, db_path):
        self.path = str(db_path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sites "
                "(site_id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, "
                "received_at TEXT NOT NULL, status TEXT NOT NULL, "
                "body_json TEXT NOT NULL)"
            )

    def _db(self):
        return sqlite3.connect(self.path, timeout=15)

    def put(self, report):
        safe = validate_site_report(report)
        received = datetime.now(timezone.utc).isoformat()
        with self._db() as db:
            prior = db.execute("SELECT observed_at FROM sites WHERE site_id = ?",
                               (safe["site_id"],)).fetchone()
            if prior and utc_time(safe["observed_at"]) < utc_time(prior[0]):
                raise ValueError("Older site report cannot overwrite newer measurements")
            db.execute(
                "INSERT INTO sites (site_id, observed_at, received_at, status, body_json) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(site_id) DO UPDATE SET "
                "observed_at=excluded.observed_at, received_at=excluded.received_at, "
                "status=excluded.status, body_json=excluded.body_json",
                (safe["site_id"], safe["observed_at"], received, safe["status"],
                 json.dumps(safe, separators=(",", ":"))),
            )
        return safe

    def list(self):
        with self._db() as db:
            rows = db.execute(
                "SELECT body_json FROM sites ORDER BY site_id LIMIT 1000").fetchall()
        return [json.loads(raw) for (raw,) in rows]

    def get(self, site_id):
        if not isinstance(site_id, str) or not SITE_RE.fullmatch(site_id):
            raise ValueError("Invalid site ID")
        with self._db() as db:
            result = db.execute("SELECT body_json FROM sites WHERE site_id=?",
                                (site_id,)).fetchone()
        return json.loads(result[0]) if result else None
