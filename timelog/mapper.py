"""Map CalendarEvents → TimeEntries using GitHub Copilot (Models API), and learn new mappings."""

import json
from openai import OpenAI

from .config import ACCOUNTS_MD, get_github_token, COPILOT_MODEL, COPILOT_BASE_URL
from .models import CalendarEvent, TimeEntry

_SYSTEM_PROMPT = """\
You are a SAP time-registration assistant.

You will be given:
1. The contents of accounts.md — the authoritative mapping of projects, keywords, and activity codes.
2. A list of calendar events for a workday.

Your task: for each event, determine the best SAP account code and activity code.

Return a JSON array (one object per event, in the same order). Each object must have:
  - "account_code": string  (from accounts.md, or "UNCLEAR" if confidence < 0.7)
  - "activity_code": string (e.g. "D100")
  - "hours": number         (same as the event duration_hours)
  - "confidence": number    (0.0 – 1.0)
  - "notes": string         (brief reasoning, or "" if obvious)

Rules:
- If confidence < 0.7, set account_code to "UNCLEAR".
- Never invent account codes not present in accounts.md.
- Respond with valid JSON only — no markdown fences, no extra text.
"""


def load_accounts_md() -> str:
    """Load accounts.md content as a string."""
    return ACCOUNTS_MD.read_text(encoding="utf-8")


def map_events(events: list[CalendarEvent]) -> list[TimeEntry]:
    """Use OpenAI to map *events* to TimeEntry objects (confirmed=False)."""
    if not events:
        return []

    token = get_github_token()
    if not token:
        raise RuntimeError("Not authenticated. Run `python -m timelog auth login` first.")
    client = OpenAI(
        base_url=COPILOT_BASE_URL,
        api_key=token,
    )
    accounts_content = load_accounts_md()

    events_payload = [
        {
            "index": i,
            "subject": e.subject,
            "duration_hours": e.duration_hours,
            "categories": e.categories,
            "body_snippet": e.body[:300],
        }
        for i, e in enumerate(events)
    ]

    user_message = (
        f"## accounts.md\n\n{accounts_content}\n\n"
        f"## Events\n\n{json.dumps(events_payload, indent=2)}"
    )

    response = client.chat.completions.create(
        model=COPILOT_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content or "[]"
    mappings: list[dict] = json.loads(raw)

    entries: list[TimeEntry] = []
    for event, mapping in zip(events, mappings):
        entries.append(
            TimeEntry(
                event=event,
                account_code=mapping.get("account_code", "UNCLEAR"),
                activity_code=mapping.get("activity_code", ""),
                hours=mapping.get("hours", event.duration_hours),
                confirmed=False,
                notes=mapping.get("notes", ""),
            )
        )
    return entries


def update_accounts_md(event_subject: str, account_code: str, activity_code: str) -> None:
    """Append a learned mapping to the Mapping Rules section of accounts.md."""
    content = ACCOUNTS_MD.read_text(encoding="utf-8")
    new_line = f'- "{event_subject}" → {account_code} | {activity_code}\n'

    marker = "<!-- The tool appends learned mappings here when you confirm a new mapping -->"
    if marker in content:
        content = content.replace(marker, marker + "\n" + new_line, 1)
    else:
        content = content.rstrip() + "\n" + new_line

    ACCOUNTS_MD.write_text(content, encoding="utf-8")
