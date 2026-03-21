"""Typer CLI — entry point for the timelog tool."""

import asyncio
import datetime
import re
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import config
from .models import TimeEntry

app = typer.Typer(help="Outlook → SAP time logging assistant", add_completion=False)
daemon_app = typer.Typer(help="Manage background reminder tasks.")
auth_app = typer.Typer(help="Authenticate with GitHub (Copilot Models API).")
app.add_typer(daemon_app, name="daemon")
app.add_typer(auth_app, name="auth")

console = Console()


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version
        console.print(f"timelog {version('timelog')}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _confidence_badge(confidence: float) -> str:
    if confidence >= 0.8:
        return f"[bold green]{confidence:.0%}[/]"
    if confidence >= 0.6:
        return f"[bold yellow]{confidence:.0%}[/]"
    return f"[bold red]{confidence:.0%}[/]"


def _entries_table(entries: list[TimeEntry], show_confidence: bool = False) -> Table:
    table = Table(box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Event", style="cyan")
    table.add_column("Account", style="magenta")
    table.add_column("Activity", style="blue")
    table.add_column("Hours", justify="right", style="green")
    if show_confidence:
        table.add_column("Confidence")
    table.add_column("Notes", style="dim")

    for i, entry in enumerate(entries, 1):
        row = [
            str(i),
            entry.event.subject,
            entry.account_code,
            entry.activity_code,
            str(entry.hours),
        ]
        if show_confidence:
            row.append(_confidence_badge(float(entry.notes.split("conf:")[-1]) if "conf:" in entry.notes else 1.0))
        row.append(entry.notes)
        table.add_row(*row)

    return table


def _parse_accounts_from_md() -> list[dict]:
    """Extract account codes and names from accounts.md for interactive prompts."""
    accounts = []
    content = config.ACCOUNTS_MD.read_text(encoding="utf-8")
    for match in re.finditer(
        r"###\s+(\S+)\s+·\s+(.+)\n.*?\*\*Default Activity:\*\*\s+(\w+)",
        content,
        re.DOTALL,
    ):
        accounts.append(
            {
                "code": match.group(1).strip(),
                "name": match.group(2).strip(),
                "activity": match.group(3).strip(),
            }
        )
    return accounts


def _run_log_for_date(target_date: datetime.date) -> bool:
    """Run the full Outlook→AI→SAP log flow for *target_date*. Returns True if submitted."""
    from .db import mark_submitted, save_entries
    from .mapper import map_events, update_accounts_md
    from .outlook import get_events
    from .sap import submit_entries

    console.print(Panel(f"📅  Fetching Outlook events for [bold]{target_date}[/]", expand=False))

    # --- 1. Pull events ---
    try:
        events = get_events(target_date)
    except RuntimeError as exc:
        console.print(f"[red]❌ {exc}[/]")
        return False

    if not events:
        console.print("[yellow]No calendar events found for that date.[/]")
        return False

    event_table = Table(box=box.SIMPLE_HEAD, show_lines=True)
    event_table.add_column("Subject", style="cyan")
    event_table.add_column("Start", style="dim")
    event_table.add_column("Duration", justify="right", style="green")
    for e in events:
        event_table.add_row(e.subject, e.start.strftime("%H:%M"), f"{e.duration_hours}h")
    console.print(event_table)

    # --- 2. LLM mapping ---
    console.print("\n🤖  Mapping events with AI…")
    try:
        entries = map_events(events)
    except Exception as exc:
        console.print(f"[red]❌ LLM mapping failed:[/] {exc}")
        return False

    console.print("\n[bold]Mapped entries:[/]")
    console.print(_entries_table(entries, show_confidence=False))

    # --- 3. Resolve UNCLEAR entries ---
    accounts = _parse_accounts_from_md()
    for entry in entries:
        if entry.account_code != "UNCLEAR":
            continue

        console.print(
            Panel(
                f"[yellow]❓ Cannot map:[/] [bold]{entry.event.subject}[/]\n"
                f"Notes: {entry.notes}",
                title="Manual mapping needed",
                expand=False,
            )
        )

        for i, acct in enumerate(accounts, 1):
            console.print(f"  [dim]{i}.[/] [magenta]{acct['code']}[/] — {acct['name']}  [dim](default: {acct['activity']})[/]")

        choice = typer.prompt("Pick account number (or type account code directly)")

        if choice.isdigit() and 1 <= int(choice) <= len(accounts):
            picked = accounts[int(choice) - 1]
            entry.account_code = picked["code"]
            entry.activity_code = picked["activity"]
        else:
            entry.account_code = choice.upper()
            entry.activity_code = typer.prompt("Activity code (e.g. D100)")

        update_accounts_md(entry.event.subject, entry.account_code, entry.activity_code)
        console.print("[green]✔ Saved mapping to accounts.md[/]")
        entry.confirmed = True

    # --- 4. Persist draft, then ask to submit ---
    save_entries(target_date, entries)

    console.print("\n[bold]Final entries:[/]")
    console.print(_entries_table(entries))

    submit = typer.confirm("\nSubmit to SAP?", default=False)
    if not submit:
        console.print("[dim]Entries saved as partial — run again to submit.[/]")
        return False

    console.print("\n🚀  Submitting to SAP Fiori…")
    try:
        asyncio.run(submit_entries(entries))
        mark_submitted(target_date)
        console.print("[bold green]✅ All entries submitted![/]")
        return True
    except Exception as exc:
        console.print(f"[red]❌ SAP submission failed:[/] {exc}")
        return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def log(
    date: Optional[str] = typer.Argument(
        None,
        help="Date to log (YYYY-MM-DD). Defaults to today.",
    )
) -> None:
    """Pull Outlook events, map to SAP entries, and optionally submit."""
    from .db import init_db

    init_db()
    target_date = datetime.date.today()
    if date:
        try:
            target_date = datetime.date.fromisoformat(date)
        except ValueError:
            console.print(f"[red]Invalid date format:[/] {date}. Use YYYY-MM-DD.")
            raise typer.Exit(1)

    _run_log_for_date(target_date)


@app.command()
def status(
    weeks: int = typer.Option(2, "--weeks", "-w", help="Number of weeks to show."),
) -> None:
    """Show time logging status for recent weeks."""
    from .db import get_missing_days, get_week_summary, init_db

    init_db()
    today = datetime.date.today()
    current_monday = today - datetime.timedelta(days=today.weekday())

    for w in range(weeks - 1, -1, -1):
        week_start = current_monday - datetime.timedelta(weeks=w)
        week_end = week_start + datetime.timedelta(days=4)
        label = "This week" if w == 0 else ("Last week" if w == 1 else f"{w} weeks ago")
        summary = get_week_summary(week_start)

        table = Table(
            title=f"{label}  ·  {week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}",
            box=box.ROUNDED,
            show_lines=True,
        )
        table.add_column("Day", style="bold", min_width=9)
        table.add_column("Date", style="dim")
        table.add_column("Status")
        table.add_column("Hours", justify="right")

        total_logged = 0.0
        total_expected = 0.0
        complete_days = 0
        missing_count = 0

        for day_info in summary:
            d: datetime.date = day_info["date"]
            s = day_info["status"]
            lh = day_info["logged_hours"]
            eh = day_info["expected_hours"]

            if s == "logged":
                status_str = "[bold green]✅ logged[/]"
                hours_str = f"[green]{lh}h[/]"
                total_logged += lh
                total_expected += eh
                complete_days += 1
            elif s == "partial":
                status_str = "[bold yellow]⚠️  partial[/]"
                hours_str = f"[yellow]{lh}h / {eh}h[/]"
                total_logged += lh
                total_expected += eh
                missing_count += 1
            elif s == "pending":
                if d > today:
                    status_str = "[dim]— future[/]"
                    hours_str = "[dim]—[/]"
                else:
                    status_str = "[bold red]❌ missing[/]"
                    hours_str = f"[red]0h / {eh}h[/]"
                    total_expected += eh
                    missing_count += 1
            elif s == "vacation":
                status_str = "[bold blue]🏖️  vacation[/]"
                hours_str = "[blue]—[/]"
            elif s in ("holiday", "skipped"):
                status_str = f"[dim]➖ {s}[/]"
                hours_str = "[dim]—[/]"
            else:
                status_str = f"[dim]{s}[/]"
                hours_str = "[dim]—[/]"

            table.add_row(d.strftime("%A"), d.strftime("%Y-%m-%d"), status_str, hours_str)

        console.print(table)

        if total_expected > 0:
            console.print(
                f"  [bold]{label}:[/] {total_logged}h / {total_expected}h logged  "
                f"([green]{complete_days} day{'s' if complete_days != 1 else ''} complete[/], "
                f"[red]{missing_count} missing[/])\n"
            )

    # Warn about older unlogged days beyond the shown window
    lookback_start = current_monday - datetime.timedelta(weeks=max(weeks, 4))
    shown_start = current_monday - datetime.timedelta(weeks=weeks - 1)
    older_missing = [
        d for d in get_missing_days(lookback_start, shown_start - datetime.timedelta(days=1))
    ]
    if older_missing:
        console.print("[bold yellow]⚠️  Older unlogged days:[/]")
        for d in older_missing:
            console.print(f"  [red]• {d.strftime('%A, %Y-%m-%d')}[/]")
        console.print("\n  Run [bold]timelog catchup[/] to log these days.")


@app.command()
def catchup(
    from_date: Optional[str] = typer.Option(
        None, "--from", help="Start date (YYYY-MM-DD). Defaults to 30 days ago."
    ),
) -> None:
    """Catch up on missed days interactively."""
    from .db import get_missing_days, init_db, set_day_status

    init_db()
    today = datetime.date.today()

    if from_date:
        try:
            since = datetime.date.fromisoformat(from_date)
        except ValueError:
            console.print(f"[red]Invalid date format:[/] {from_date}. Use YYYY-MM-DD.")
            raise typer.Exit(1)
    else:
        since = today - datetime.timedelta(days=30)

    missing = get_missing_days(since, today - datetime.timedelta(days=1))

    if not missing:
        console.print("[bold green]✅ All caught up! No missing days found.[/]")
        return

    console.print(
        Panel(
            f"Found [bold red]{len(missing)} missing day{'s' if len(missing) != 1 else ''}[/]:\n"
            + "\n".join(f"  • {d.strftime('%A, %Y-%m-%d')}" for d in missing),
            title="Missing days",
            expand=False,
        )
    )

    submitted = 0
    skipped = 0

    for idx, day in enumerate(missing, 1):
        console.print(f"\n[bold]Day {idx} of {len(missing)}[/] — {day.strftime('%A %Y-%m-%d')}")
        pull = typer.confirm("  Pull Outlook events?", default=True)

        if pull:
            if _run_log_for_date(day):
                submitted += 1
        else:
            action = typer.prompt("  Action  [s=skip  v=vacation  q=quit]", default="s")
            action = action.strip().lower()
            if action == "v":
                set_day_status(day, "vacation")
                console.print(f"  [blue]🏖️  Marked {day} as vacation.[/]")
                skipped += 1
            elif action == "q":
                console.print("[dim]Catchup stopped.[/]")
                break
            else:
                set_day_status(day, "skipped")
                console.print(f"  [dim]➖ Skipped {day}.[/]")
                skipped += 1

    console.print(
        Panel(
            f"[bold green]{submitted} submitted[/]  ·  [dim]{skipped} skipped[/]",
            title="Catchup complete",
            expand=False,
        )
    )


@app.command()
def vacation(
    start: str = typer.Argument(..., help="Start date (YYYY-MM-DD)."),
    end: Optional[str] = typer.Argument(None, help="End date (YYYY-MM-DD). Defaults to start date."),
) -> None:
    """Mark workdays in a date range as vacation."""
    from .db import init_db, set_day_status

    init_db()
    try:
        start_date = datetime.date.fromisoformat(start)
        end_date = datetime.date.fromisoformat(end) if end else start_date
    except ValueError as exc:
        console.print(f"[red]Invalid date format:[/] {exc}. Use YYYY-MM-DD.")
        raise typer.Exit(1)

    if end_date < start_date:
        console.print("[red]End date must be on or after start date.[/]")
        raise typer.Exit(1)

    marked = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            set_day_status(current, "vacation")
            marked.append(current)
        current += datetime.timedelta(days=1)

    if not marked:
        console.print("[yellow]No workdays in that range to mark.[/]")
        return

    table = Table(title="Vacation days registered", box=box.ROUNDED, show_lines=True)
    table.add_column("Day", style="bold")
    table.add_column("Date", style="blue")
    table.add_column("Status")
    for d in marked:
        table.add_row(d.strftime("%A"), d.isoformat(), "[bold blue]🏖️  vacation[/]")
    console.print(table)
    console.print(f"[bold blue]✔ {len(marked)} day{'s' if len(marked) != 1 else ''} marked as vacation.[/]")


@app.command()
def skip(
    date: Optional[str] = typer.Argument(None, help="Date to skip (YYYY-MM-DD). Defaults to today."),
    note: str = typer.Option("", "--note", "-n", help="Optional note (e.g. 'Public holiday')."),
) -> None:
    """Mark a day as skipped (no time entry needed)."""
    from .db import init_db, set_day_status

    init_db()
    target = datetime.date.today()
    if date:
        try:
            target = datetime.date.fromisoformat(date)
        except ValueError:
            console.print(f"[red]Invalid date format:[/] {date}. Use YYYY-MM-DD.")
            raise typer.Exit(1)

    set_day_status(target, "skipped", notes=note)
    note_str = f"  [dim]{note}[/]" if note else ""
    console.print(f"[dim]➖ {target.strftime('%A, %Y-%m-%d')} marked as skipped.{note_str}[/]")


@app.command()
def trigger(
    name: str = typer.Argument(..., help="Trigger name: eod or morning."),
) -> None:
    """Run a scheduled trigger (called by Task Scheduler — silent, no Rich output)."""
    from .triggers import run_eod_trigger, run_morning_trigger

    if name == "eod":
        run_eod_trigger()
    elif name == "morning":
        run_morning_trigger()
    else:
        typer.echo(f"Unknown trigger: {name}. Use 'eod' or 'morning'.", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# daemon subcommands
# ---------------------------------------------------------------------------

@daemon_app.command("install")
def daemon_install() -> None:
    """Install scheduled reminder tasks (per-day EOD + login morning prompt)."""
    from .scheduler import install_tasks

    console.print(Panel("Installing timelog scheduled tasks…", style="bold cyan"))
    install_tasks()
    console.print("\n[dim]EOD times: Mon/Tue/Wed 16:00 · Thu 15:30 · Fri 14:00[/]")
    console.print("[dim]Morning: fires on Windows login (weekdays)[/]")


@daemon_app.command("uninstall")
def daemon_uninstall() -> None:
    """Remove scheduled reminder tasks."""
    from .scheduler import uninstall_tasks

    uninstall_tasks()


@daemon_app.command("status")
def daemon_status() -> None:
    """Show status of all scheduled reminder tasks."""
    from .scheduler import MORNING_TASK, get_task_status

    task_info = get_task_status()
    table = Table(title="Scheduled Tasks", box=box.ROUNDED, show_lines=True)
    table.add_column("Task", style="bold")
    table.add_column("Trigger", style="cyan")
    table.add_column("Installed")
    table.add_column("Next Run", style="dim")
    table.add_column("Last Run", style="dim")

    eod_labels = {
        "timelog-eod-mon": "Mon 16:00",
        "timelog-eod-tue": "Tue 16:00",
        "timelog-eod-wed": "Wed 16:00",
        "timelog-eod-thu": "Thu 15:30",
        "timelog-eod-fri": "Fri 14:00",
    }
    for task_name, trigger_label in eod_labels.items():
        info = task_info.get(task_name, {})
        installed_str = "[green]✔[/]" if info.get("installed") else "[red]✘[/]"
        table.add_row(task_name, trigger_label, installed_str, info.get("next_run", "N/A"), info.get("last_run", "N/A"))

    info = task_info.get(MORNING_TASK, {})
    installed_str = "[green]✔[/]" if info.get("installed") else "[red]✘[/]"
    table.add_row(MORNING_TASK, "On login (weekdays)", installed_str, info.get("next_run", "N/A"), info.get("last_run", "N/A"))

    console.print(table)


# ---------------------------------------------------------------------------
# Existing commands
# ---------------------------------------------------------------------------

@app.command()
def accounts() -> None:
    """Show all SAP accounts defined in accounts.md."""
    if not config.ACCOUNTS_MD.exists():
        console.print("[red]accounts.md not found.[/] Run from the repo root.")
        raise typer.Exit(1)

    accts = _parse_accounts_from_md()
    table = Table(title="SAP Accounts", box=box.ROUNDED, show_lines=True)
    table.add_column("Code", style="magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Default Activity", style="blue")
    for a in accts:
        table.add_row(a["code"], a["name"], a["activity"])
    console.print(table)


@app.command()
def init() -> None:
    """First-time setup: configure timelog interactively, then validate everything."""
    import subprocess
    import sys

    from .auth import is_authenticated

    console.print(Panel(
        f"[bold]Welcome to timelog![/]\n\nConfig and data will be stored in [cyan]{config.CONFIG_DIR}[/]",
        border_style="cyan",
    ))

    # ── Step 1: Collect config values ────────────────────────────────────────
    console.print("\n[bold]Step 1 of 4 · Configuration[/]")

    new_values: dict[str, str] = {}

    client_id = config.GITHUB_CLIENT_ID
    if not client_id:
        console.print(
            "\n  To get a GitHub OAuth Client ID:\n"
            "  1. Go to [link]https://github.com/settings/developers[/link]\n"
            "  2. Click [bold]New OAuth App[/bold]\n"
            "  3. Name: timelog  |  Homepage: anything  |  Callback URL: leave blank\n"
            "  4. Paste the Client ID below\n"
        )
    client_id = typer.prompt(
        "  GitHub OAuth Client ID",
        default=client_id or "",
        show_default=bool(client_id),
    )
    new_values["GITHUB_CLIENT_ID"] = client_id

    sap_url = typer.prompt("  SAP Fiori URL", default=config.SAP_URL or "")
    new_values["SAP_URL"] = sap_url

    sap_user = typer.prompt("  SAP username", default=config.SAP_USERNAME or "")
    new_values["SAP_USERNAME"] = sap_user

    model = typer.prompt("  Copilot model", default=config.COPILOT_MODEL or "gpt-4o")
    new_values["COPILOT_MODEL"] = model

    config.save_config(new_values)
    console.print(f"  [green]✔[/] Config saved to [cyan]{config.CONFIG_FILE}[/]")

    # ── Step 2: Seed accounts.md ─────────────────────────────────────────────
    console.print("\n[bold]Step 2 of 4 · accounts.md[/]")
    if config.ACCOUNTS_MD.exists():
        console.print(f"  [green]✔[/] accounts.md already exists at [cyan]{config.ACCOUNTS_MD}[/]")
    else:
        if config._TEMPLATE_ACCOUNTS_MD.exists():
            import shutil
            shutil.copy(config._TEMPLATE_ACCOUNTS_MD, config.ACCOUNTS_MD)
            console.print(f"  [green]✔[/] accounts.md created at [cyan]{config.ACCOUNTS_MD}[/]")
            console.print("  [dim]Edit it to add your real SAP accounts and keywords.[/]")
        else:
            console.print(f"  [yellow]⚠[/] Template not found — create [cyan]{config.ACCOUNTS_MD}[/] manually.")

    # ── Step 3: GitHub auth ───────────────────────────────────────────────────
    console.print("\n[bold]Step 3 of 4 · GitHub authentication[/]")
    if is_authenticated():
        console.print("  [green]✔[/] Already authenticated — token in Windows Credential Manager")
    else:
        do_login = typer.confirm("  Authenticate with GitHub now?", default=True)
        if do_login:
            from .auth import login as _gh_login
            try:
                console.print(Panel(
                    "Opening [bold]github.com[/bold] in your browser.\nEnter the code shown below to authorize timelog.",
                    border_style="cyan",
                ))
                _gh_login(client_id, open_browser=True)
                console.print("  [green]✔[/] Authenticated — token saved to Windows Credential Manager")
            except RuntimeError as exc:
                console.print(f"  [red]✘[/] {exc}")
        else:
            console.print("  [dim]Skipped — run `timelog auth login` when ready.[/]")

    # ── Step 4: Health checks ─────────────────────────────────────────────────
    console.print("\n[bold]Step 4 of 4 · Health checks[/]")
    ok = True

    try:
        import win32com.client  # noqa: F401
        outlook = win32com.client.Dispatch("Outlook.Application")
        outlook.GetNamespace("MAPI")
        console.print("  [green]✔[/] Outlook connection OK")
    except ImportError:
        console.print("  [red]✘[/] pywin32 not installed")
        ok = False
    except Exception as exc:
        console.print(f"  [yellow]⚠[/] Outlook not reachable: {exc}")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        console.print("  [green]✔[/] Playwright Chromium OK")
    except Exception:
        console.print("  [yellow]⚠[/] Playwright Chromium not installed — installing now...")
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print("  [green]✔[/] Playwright Chromium installed")
        else:
            console.print(f"  [red]✘[/] Playwright install failed: {result.stderr.strip()}")
            ok = False

    # ── Done ──────────────────────────────────────────────────────────────────
    console.print()
    if ok:
        console.print(Panel(
            "[bold green]You're all set! 🎉[/]\n\n"
            f"  Edit your accounts:  [cyan]{config.ACCOUNTS_MD}[/]\n"
            "  Set up reminders:    [cyan]timelog daemon install[/]\n"
            "  Log today:           [cyan]timelog log[/]",
            border_style="green",
        ))
    else:
        console.print(Panel("[bold yellow]Setup complete with warnings — see above.[/]", border_style="yellow"))


# ---------------------------------------------------------------------------
# auth subcommands
# ---------------------------------------------------------------------------

@auth_app.command("login")
def auth_login() -> None:
    """Authenticate with GitHub via browser — stores token in Windows Credential Manager."""
    from .auth import is_authenticated, login

    if is_authenticated():
        console.print("[green]✔[/] Already authenticated. Use `timelog auth logout` to switch accounts.")
        return

    if not config.GITHUB_CLIENT_ID:
        console.print(Panel(
            "[red]GITHUB_CLIENT_ID is not set.[/]\n\n"
            "1. Go to [link]https://github.com/settings/developers[/link]\n"
            "2. Click [bold]New OAuth App[/bold]\n"
            "3. Set any name/homepage, leave callback URL blank\n"
            "4. Copy the [bold]Client ID[/bold] and run [bold]timelog init[/bold] to save it",
            title="Setup required", border_style="yellow",
        ))
        raise typer.Exit(1)

    console.print(Panel(
        "Opening [bold]github.com[/bold] in your browser.\n"
        "Enter the code shown below to authorize timelog.",
        title="GitHub Login", border_style="cyan",
    ))

    try:
        token = login(config.GITHUB_CLIENT_ID, open_browser=True)
        _ = token  # stored in keyring by login()
        console.print("\n[bold green]✔ Authenticated successfully![/] Token saved to Windows Credential Manager.")
    except RuntimeError as exc:
        console.print(f"[red]✘ {exc}[/]")
        raise typer.Exit(1)


@auth_app.command("logout")
def auth_logout() -> None:
    """Remove stored GitHub token from Windows Credential Manager."""
    from .auth import delete_token, is_authenticated

    if not is_authenticated():
        console.print("[yellow]Not currently authenticated.[/]")
        return

    delete_token()
    console.print("[green]✔[/] Logged out — token removed from Credential Manager.")


@auth_app.command("status")
def auth_status() -> None:
    """Show current GitHub authentication status."""
    from .auth import get_token, is_authenticated

    if is_authenticated():
        token = get_token() or ""
        preview = f"{token[:8]}…{token[-4:]}" if len(token) > 12 else "***"
        console.print(f"[green]✔ Authenticated[/] · token: [dim]{preview}[/] · stored in Windows Credential Manager")
    else:
        console.print("[red]✘ Not authenticated[/] · run `python -m timelog auth login`")


if __name__ == "__main__":
    app()
