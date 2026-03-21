"""Pydantic models for calendar events and SAP time entries."""

from pydantic import BaseModel
from datetime import datetime


class CalendarEvent(BaseModel):
    subject: str
    start: datetime
    end: datetime
    duration_hours: float
    body: str = ""
    categories: list[str] = []


class TimeEntry(BaseModel):
    event: CalendarEvent
    account_code: str
    activity_code: str
    hours: float
    confirmed: bool = False
    notes: str = ""
