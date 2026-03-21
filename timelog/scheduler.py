"""Windows Task Scheduler integration via schtasks.exe (no admin required for user tasks)."""

import csv
import io
import subprocess
import sys

MORNING_TASK = "timelog-morning"

# Per-weekday EOD task names and their trigger times.
EOD_TASKS: dict[str, str] = {
    "timelog-eod-mon": "16:00",
    "timelog-eod-tue": "16:00",
    "timelog-eod-wed": "16:00",
    "timelog-eod-thu": "15:30",
    "timelog-eod-fri": "14:00",
}

_DAY_FLAGS = {
    "timelog-eod-mon": "MON",
    "timelog-eod-tue": "TUE",
    "timelog-eod-wed": "WED",
    "timelog-eod-thu": "THU",
    "timelog-eod-fri": "FRI",
}

ALL_TASKS = list(EOD_TASKS) + [MORNING_TASK]


def _python_exe() -> str:
    return sys.executable


def _cmd(trigger: str) -> str:
    return f'"{_python_exe()}" -m timelog trigger {trigger}'


def install_tasks() -> None:
    """Install per-day EOD tasks (WEEKLY, one day each) + ONLOGON morning task."""

    # --- EOD tasks: one per weekday at the correct time ---
    for task_name, run_time in EOD_TASKS.items():
        day_flag = _DAY_FLAGS[task_name]
        result = subprocess.run(
            [
                "schtasks", "/Create",
                "/TN", task_name,
                "/TR", _cmd("eod"),
                "/SC", "WEEKLY",
                "/D", day_flag,
                "/ST", run_time,
                "/F", "/IT",
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"✔ {task_name}  ({day_flag} at {run_time})")
        else:
            print(f"✘ {task_name}: {result.stderr.strip()}")
            print("  Tip: Run in an interactive terminal, not a service.")

    # --- Morning task: daily at 08:00, Mon–Fri ---
    # ONLOGON requires elevated permissions on some systems; a fixed early time is equivalent.
    # Weekend check is handled inside run_morning_trigger() so it's silent on Sat/Sun.
    result = subprocess.run(
        [
            "schtasks", "/Create",
            "/TN", MORNING_TASK,
            "/TR", _cmd("morning"),
            "/SC", "WEEKLY",
            "/D", "MON,TUE,WED,THU,FRI",
            "/ST", "08:00",
            "/F", "/IT",
        ],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"✔ {MORNING_TASK}  (Mon–Fri at 08:00)")
    else:
        print(f"✘ {MORNING_TASK}: {result.stderr.strip()}")


def uninstall_tasks() -> None:
    """Remove all timelog scheduled tasks."""
    for task_name in ALL_TASKS:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"✔ Removed '{task_name}'")
        else:
            print(f"✘ Could not remove '{task_name}': {result.stderr.strip()}")


def _query_task(task_name: str) -> dict:
    probe = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name],
        capture_output=True, text=True,
    )
    if probe.returncode != 0:
        return {"installed": False, "next_run": "N/A", "last_run": "N/A", "last_result": "N/A"}

    verbose = subprocess.run(
        ["schtasks", "/Query", "/FO", "CSV", "/V", "/TN", task_name],
        capture_output=True, text=True,
    )
    fields: dict = {}
    if verbose.returncode == 0 and verbose.stdout.strip():
        try:
            for row in csv.DictReader(io.StringIO(verbose.stdout)):
                fields = dict(row)
                break
        except Exception:
            pass

    return {
        "installed": True,
        "next_run": fields.get("Next Run Time", "N/A"),
        "last_run": fields.get("Last Run Time", "N/A"),
        "last_result": fields.get("Last Result", "N/A"),
    }


def get_task_status() -> dict:
    """Return status dict keyed by task name for all timelog tasks."""
    return {name: _query_task(name) for name in ALL_TASKS}
