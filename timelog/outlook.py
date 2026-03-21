"""Read Outlook calendar events via win32com (Windows only)."""

import datetime
from .models import CalendarEvent


def get_events(date: datetime.date) -> list[CalendarEvent]:
    """Return non-all-day CalendarEvents for *date* from the default Outlook calendar."""
    try:
        import win32com.client
    except ImportError:
        raise RuntimeError("pywin32 is not installed. Run: pip install pywin32")

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
    except Exception as exc:
        raise RuntimeError(
            "Could not connect to Outlook. Make sure Outlook is running."
        ) from exc

    namespace = outlook.GetNamespace("MAPI")
    calendar = namespace.GetDefaultFolder(9)  # olFolderCalendar = 9
    items = calendar.Items

    items.IncludeRecurrences = True
    items.Sort("[Start]")

    start_str = date.strftime("%m/%d/%Y 00:00 AM")
    end_str = date.strftime("%m/%d/%Y 11:59 PM")
    items = items.Restrict(
        f"[Start] >= '{start_str}' AND [Start] <= '{end_str}'"
    )

    events: list[CalendarEvent] = []
    for item in items:
        if getattr(item, "AllDayEvent", False):
            continue

        start: datetime.datetime = item.Start
        end: datetime.datetime = item.End

        # win32com returns pywintypes.datetime — convert to stdlib datetime
        start = datetime.datetime(
            start.year, start.month, start.day,
            start.hour, start.minute, start.second,
        )
        end = datetime.datetime(
            end.year, end.month, end.day,
            end.hour, end.minute, end.second,
        )

        duration_hours = round((end - start).total_seconds() / 3600, 2)

        categories_raw = getattr(item, "Categories", "") or ""
        categories = [c.strip() for c in categories_raw.split(";") if c.strip()]

        events.append(
            CalendarEvent(
                subject=item.Subject or "(no subject)",
                start=start,
                end=end,
                duration_hours=duration_hours,
                body=getattr(item, "Body", "") or "",
                categories=categories,
            )
        )

    return events
