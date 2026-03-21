"""Logic for scheduled trigger execution (called by Task Scheduler — no interactive output)."""

import datetime

from .db import get_day_status, get_missing_days, init_db
from .notify import eod_prompt, morning_prompt


def run_eod_trigger() -> None:
    """Called by Task Scheduler at 16:00. Sends EOD toast if today is unlogged."""
    init_db()
    today = datetime.date.today()
    status = get_day_status(today)
    if status in ("logged", "vacation", "holiday", "weekend"):
        return
    eod_prompt(missing_today=(status == "pending"), partial_today=(status == "partial"))


def run_morning_trigger() -> None:
    """Called by Task Scheduler on login. Skips weekends, then toasts for missing days."""
    init_db()
    today = datetime.date.today()
    # ONLOGON fires every day — skip weekends silently.
    if today.weekday() >= 5:
        return
    since = today - datetime.timedelta(days=30)
    until = today - datetime.timedelta(days=1)
    missing = get_missing_days(since, until)
    if missing:
        morning_prompt(missing)
