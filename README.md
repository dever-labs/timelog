# timelog

> Stop logging time manually. timelog reads your Outlook calendar, uses GitHub Copilot to map meetings to SAP accounts, and submits your timesheet automatically.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![Platform Windows](https://img.shields.io/badge/platform-windows-lightgrey)
![License](https://img.shields.io/github/license/dever-labs/timelog)
![Latest release](https://img.shields.io/github/v/release/dever-labs/timelog)

---

## How it works

1. 📅 Pulls your Outlook calendar events for the day
2. 🤖 GitHub Copilot maps each event → SAP account + activity code (using `accounts.md` as context)
3. ✅ You confirm (or correct) the mappings — unclear ones are saved back to `accounts.md` so it learns
4. 🚀 Playwright automates SAP Fiori and submits the timesheet

---

## Prerequisites

- Windows (uses Outlook COM API and Windows Credential Manager)
- Python 3.11+
- Outlook desktop installed and running
- SAP Fiori access (URL + credentials)
- GitHub account with Copilot Enterprise access
- GitHub CLI (`gh`) recommended for install

---

## Installation

```powershell
irm https://raw.githubusercontent.com/dever-labs/timelog/main/install.ps1 | iex
```

What the installer does:

- Installs [pipx](https://pipx.pypa.io/) if it isn't already present
- Installs `timelog` globally via pipx
- Installs the Playwright Chromium browser

---

## First-time setup

1. **Run `timelog init`** — it walks you through everything interactively:
   ```powershell
   timelog init
   ```
   This will ask for your GitHub OAuth Client ID, SAP URL, and username, then save them to `~/.timelog/config.env`. It also seeds your `accounts.md`, authenticates with GitHub, and installs Playwright Chromium — all in one go.

   > **To get a GitHub OAuth Client ID:** go to [github.com/settings/developers](https://github.com/settings/developers) → *New OAuth App*. Name it `timelog`, leave the callback URL blank. Copy the **Client ID** when prompted.

2. **Edit `accounts.md`** at `~/.timelog/accounts.md` — add your real SAP account codes, activity codes, and keywords (see [accounts.md](#accountsmd) below).

3. **Install daily reminders:**
   ```powershell
   timelog schedule install
   ```

---

## Daily workflow

timelog fits into your day without extra effort:

- **Morning login** → a toast notification fires if anything is missing from the last 30 days.
- **End of day** → a toast fires at your configured cutoff time (Mon–Wed 16:00, Thu 15:30, Fri 14:00).
- Click the toast (or run the command yourself) to log the day or catch up:
  ```powershell
  timelog log          # log today
  timelog catchup      # walk through all unlogged days
  ```

---

## Commands — full reference

| Command | Description |
|---------|-------------|
| `timelog log [DATE]` | Log today (or a specific date) — Outlook → AI → SAP |
| `timelog status` | Weekly dashboard showing logged/missing/vacation days |
| `timelog catchup` | Walk through all unlogged days interactively |
| `timelog vacation <start> [end]` | Mark a date range as vacation |
| `timelog skip [DATE]` | Mark a day as intentionally not logged |
| `timelog accounts` | List all SAP accounts from accounts.md |
| `timelog auth login` | Authenticate with GitHub (browser OAuth flow) |
| `timelog auth logout` | Remove stored GitHub token |
| `timelog auth status` | Check authentication status |
| `timelog init` | First-time setup and health check |
| `timelog schedule install` | Set up Windows Task Scheduler reminders |
| `timelog schedule uninstall` | Remove scheduled tasks |
| `timelog schedule status` | Show all scheduled tasks and their state |

---

## accounts.md

`accounts.md` is the heart of the system. The AI reads the **entire file** as context for every mapping decision. The more detail you add, the more accurate the automatic mapping becomes.

Minimal example:

```markdown
## Activity Codes

| Code | Name        | Description                           |
|------|-------------|---------------------------------------|
| D100 | Development | Coding, reviews, debugging            |
| M200 | Meetings    | Standups, demos, planning             |

## Accounts

### PROJ-1000 · My Main Project
- **SAP Account Code:** PROJ-1000
- **Default Activity:** D100
- **Keywords:** sprint, backend, api, feature
- **Aliases:** alpha
- **Notes:** Core development. D100 for dev tasks, M200 for project meetings.
```

When you resolve an **UNCLEAR** entry interactively, timelog automatically appends the confirmed mapping to `accounts.md` under *Mapping Rules* so it won't ask again.

---

## SAP Fiori selectors

`timelog/sap.py` contains Playwright selectors marked with `TODO`. These are the only fields you need to adapt to your SAP instance:

1. Open your SAP Fiori timesheet URL in a browser.
2. Open **DevTools → Inspector** and identify the real field IDs/labels for date, account, activity, and hours.
3. Replace the `TODO` placeholders in `sap.py` with those selectors.

This is a one-time step per SAP environment.

---

## Updating timelog

```powershell
# Reinstall the latest release
irm https://raw.githubusercontent.com/dever-labs/timelog/main/install.ps1 | iex
```

Or pin a specific version:

```powershell
pipx install git+https://github.com/dever-labs/timelog.git@v1.2.0 --force
```

---

## Project structure

```
timelog/
├── accounts.md          ← Core config: edit with your SAP accounts
├── .env.example         ← Developer reference only (users run `timelog init`)
├── install.ps1          ← One-command installer
├── CHANGELOG.md
├── pyproject.toml
└── timelog/
    ├── auth.py          ← GitHub Device OAuth flow
    ├── cli.py           ← Typer CLI (all commands)
    ├── config.py        ← Configuration
    ├── db.py            ← Local SQLite state (~/.timelog/state.db)
    ├── mapper.py        ← GitHub Copilot event→account mapping
    ├── models.py        ← Pydantic data models
    ├── notify.py        ← Windows toast notifications
    ├── outlook.py       ← Outlook calendar reader (win32com)
    ├── sap.py           ← SAP Fiori Playwright automation
    ├── scheduler.py     ← Windows Task Scheduler integration
    └── triggers.py      ← EOD and morning trigger logic
```

---

## Contributing

1. Fork the repository and create a feature branch.
2. Make your changes and test locally.
3. Open a pull request against `main`.

> **Note:** `accounts.md` in the repo is a template. **Never commit real SAP account codes** — keep those in your local copy only.

---

## License

This project is released into the public domain under the [Unlicense](https://unlicense.org).
