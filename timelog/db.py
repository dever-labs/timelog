"""SQLite state database for timelog — stores day status and time entries."""

import datetime
import sqlite3
from pathlib import Path

DB_DIR = Path.home() / ".timelog"
DB_PATH = DB_DIR / "state.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS days (
    date TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    expected_hours REAL DEFAULT 7.5,
    logged_hours REAL DEFAULT 0.0,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    account_code TEXT NOT NULL,
    activity_code TEXT NOT NULL,
    hours REAL NOT NULL,
    submitted INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _conn() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    """Create DB and tables if they don't exist. Called at startup."""
    c = _conn()
    try:
        c.executescript(_SCHEMA)
        c.commit()
    finally:
        c.close()


def get_day_status(date: datetime.date) -> str:
    """Return status for a date, defaulting to 'pending' for workdays, 'weekend' for Sat/Sun."""
    if date.weekday() >= 5:
        return "weekend"
    c = _conn()
    try:
        row = c.execute("SELECT status FROM days WHERE date = ?", (date.isoformat(),)).fetchone()
    finally:
        c.close()
    return row["status"] if row else "pending"


def set_day_status(date: datetime.date, status: str, notes: str = "") -> None:
    c = _conn()
    try:
        c.execute(
            """
            INSERT INTO days (date, status, notes)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET status = excluded.status, notes = excluded.notes
            """,
            (date.isoformat(), status, notes),
        )
        c.commit()
    finally:
        c.close()


def get_logged_hours(date: datetime.date) -> float:
    c = _conn()
    try:
        row = c.execute("SELECT logged_hours FROM days WHERE date = ?", (date.isoformat(),)).fetchone()
    finally:
        c.close()
    return float(row["logged_hours"]) if row else 0.0


def save_entries(date: datetime.date, entries: list) -> None:
    """Save TimeEntry list for a date, mark day as partial. Replaces pending entries."""
    c = _conn()
    try:
        c.execute("DELETE FROM entries WHERE date = ? AND submitted = 0", (date.isoformat(),))
        total_hours = 0.0
        for entry in entries:
            c.execute(
                "INSERT INTO entries (date, account_code, activity_code, hours, notes) VALUES (?, ?, ?, ?, ?)",
                (date.isoformat(), entry.account_code, entry.activity_code, entry.hours, entry.notes),
            )
            total_hours += entry.hours
        c.execute(
            """
            INSERT INTO days (date, status, logged_hours)
            VALUES (?, 'partial', ?)
            ON CONFLICT(date) DO UPDATE SET status = 'partial', logged_hours = excluded.logged_hours
            """,
            (date.isoformat(), total_hours),
        )
        c.commit()
    finally:
        c.close()


def mark_submitted(date: datetime.date) -> None:
    """Mark all entries for date as submitted=1, update day status to 'logged'."""
    c = _conn()
    try:
        c.execute("UPDATE entries SET submitted = 1 WHERE date = ?", (date.isoformat(),))
        c.execute(
            """
            INSERT INTO days (date, status)
            VALUES (?, 'logged')
            ON CONFLICT(date) DO UPDATE SET status = 'logged'
            """,
            (date.isoformat(),),
        )
        c.commit()
    finally:
        c.close()


def get_missing_days(since: datetime.date, until: datetime.date) -> list[datetime.date]:
    """Return workdays (Mon-Fri) in range with status 'pending' or 'partial', excluding weekends."""
    missing = []
    current = since
    while current <= until:
        if current.weekday() < 5:
            if get_day_status(current) in ("pending", "partial"):
                missing.append(current)
        current += datetime.timedelta(days=1)
    return missing


def get_config(key: str, default: str = "") -> str:
    c = _conn()
    try:
        row = c.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    finally:
        c.close()
    return row["value"] if row else default


def set_config(key: str, value: str) -> None:
    c = _conn()
    try:
        c.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        c.commit()
    finally:
        c.close()


def get_week_summary(week_start: datetime.date) -> list[dict]:
    """Return list of dicts for Mon-Fri of the given week."""
    result = []
    c = _conn()
    try:
        for i in range(5):
            day = week_start + datetime.timedelta(days=i)
            row = c.execute(
                "SELECT status, logged_hours, expected_hours FROM days WHERE date = ?",
                (day.isoformat(),),
            ).fetchone()
            if row:
                result.append({
                    "date": day,
                    "status": row["status"],
                    "logged_hours": float(row["logged_hours"]),
                    "expected_hours": float(row["expected_hours"]),
                })
            else:
                result.append({
                    "date": day,
                    "status": "pending",
                    "logged_hours": 0.0,
                    "expected_hours": 7.5,
                })
    finally:
        c.close()
    return result
