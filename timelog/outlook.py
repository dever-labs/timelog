"""Read Outlook calendar events — supports classic Outlook (win32com) and new Outlook (WinRT)."""

import asyncio
import datetime

from .models import CalendarEvent

# 100-nanosecond intervals between Windows epoch (1601-01-01) and Unix epoch (1970-01-01)
_EPOCH_DIFF = 116_444_736_000_000_000


def get_events(date: datetime.date) -> list[CalendarEvent]:
    """Return non-all-day CalendarEvents for *date*. Tries classic Outlook then new Outlook."""
    try:
        return _get_events_win32com(date)
    except Exception as exc_com:
        try:
            return asyncio.run(_get_events_winrt(date))
        except Exception as exc_winrt:
            raise RuntimeError(
                "Could not read calendar from Outlook.\n"
                f"  Classic Outlook (win32com): {exc_com}\n"
                f"  New Outlook (WinRT):        {exc_winrt}\n"
                "  Make sure Outlook (classic or new) is installed and signed in."
            ) from exc_com


# ---------------------------------------------------------------------------
# Classic Outlook via win32com (Outlook desktop app)
# ---------------------------------------------------------------------------

def _get_events_win32com(date: datetime.date) -> list[CalendarEvent]:
    import win32com.client

    outlook = win32com.client.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")
    calendar = namespace.GetDefaultFolder(9)  # olFolderCalendar
    items = calendar.Items
    items.IncludeRecurrences = True
    items.Sort("[Start]")

    start_str = date.strftime("%m/%d/%Y 00:00 AM")
    end_str = date.strftime("%m/%d/%Y 11:59 PM")
    items = items.Restrict(f"[Start] >= '{start_str}' AND [Start] <= '{end_str}'")

    events: list[CalendarEvent] = []
    for item in items:
        if getattr(item, "AllDayEvent", False):
            continue
        start = item.Start
        end = item.End
        start = datetime.datetime(start.year, start.month, start.day, start.hour, start.minute)
        end = datetime.datetime(end.year, end.month, end.day, end.hour, end.minute)
        duration_hours = round((end - start).total_seconds() / 3600, 2)
        if duration_hours <= 0:
            continue
        categories_raw = getattr(item, "Categories", "") or ""
        categories = [c.strip() for c in categories_raw.split(";") if c.strip()]
        events.append(CalendarEvent(
            subject=item.Subject or "(no subject)",
            start=start,
            end=end,
            duration_hours=duration_hours,
            body=getattr(item, "Body", "")[:300],
            categories=categories,
        ))
    return events


# ---------------------------------------------------------------------------
# New Outlook via Windows.ApplicationModel.Appointments WinRT API
# ---------------------------------------------------------------------------

async def _get_events_winrt(date: datetime.date) -> list[CalendarEvent]:
    from winsdk.windows.applicationmodel.appointments import (
        AppointmentManager,
        AppointmentStoreAccessType,
    )
    from winsdk.windows.foundation import DateTime, TimeSpan

    store = await AppointmentManager.request_store_async(
        AppointmentStoreAccessType.ALL_CALENDARS_READ_ONLY
    )

    start_dt = datetime.datetime.combine(date, datetime.time.min)
    end_dt = datetime.datetime.combine(date, datetime.time.max)

    winrt_start = DateTime()
    winrt_start.universal_time = int(start_dt.timestamp() * 10_000_000) + _EPOCH_DIFF

    duration_ticks = int((end_dt - start_dt).total_seconds() * 10_000_000)
    winrt_duration = TimeSpan()
    winrt_duration.duration = duration_ticks

    appointments = await store.find_appointments_async(winrt_start, winrt_duration)

    events: list[CalendarEvent] = []
    for appt in appointments:
        if appt.all_day:
            continue

        # Convert WinRT DateTime → Python datetime
        start_unix = (appt.start_time.universal_time - _EPOCH_DIFF) / 10_000_000
        start = datetime.datetime.fromtimestamp(start_unix)
        duration_hours = round(appt.duration.duration / 10_000_000 / 3600, 2)
        if duration_hours <= 0:
            continue
        end = start + datetime.timedelta(hours=duration_hours)

        events.append(CalendarEvent(
            subject=appt.subject or "(no subject)",
            start=start,
            end=end,
            duration_hours=duration_hours,
            body=(appt.details or "")[:300],
            categories=[],
        ))
    return events
