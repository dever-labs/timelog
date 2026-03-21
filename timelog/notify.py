"""Windows toast notifications via plyer (best-effort — all errors are silent)."""


def toast(title: str, message: str, timeout: int = 10) -> None:
    """Show a desktop toast notification."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="timelog",
            app_icon=None,
            timeout=timeout,
        )
    except Exception:
        pass


def eod_prompt(missing_today: bool, partial_today: bool) -> None:
    """Send end-of-day toast depending on today's logging state."""
    if missing_today:
        toast("timelog — Log your time", "Time to log your day! Run: python -m timelog log")
    elif partial_today:
        toast(
            "timelog — Incomplete entries",
            "You have partial entries — finish logging? Run: python -m timelog log",
        )


def morning_prompt(missing_days: list) -> None:
    """Send morning toast if days are missing."""
    n = len(missing_days)
    if n == 1:
        toast(
            "timelog — Missing time log",
            "Yesterday's time log is missing. Run: python -m timelog catchup",
        )
    elif n > 1:
        toast(
            "timelog — Missing time logs",
            f"You have {n} unlogged days. Run: python -m timelog catchup",
        )
