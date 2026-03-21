# Changelog

All notable changes to timelog are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.1.0] - 2026-03-21

### Added
- Outlook calendar → SAP Fiori time entry automation
- AI mapping of calendar events to SAP accounts via GitHub Copilot Models API
- GitHub Device Authorization Flow — token stored in Windows Credential Manager
- Daily reminders via Windows Task Scheduler (per-day EOD times + login trigger)
- `timelog log` — interactive daily logging with AI suggestions
- `timelog status` — weekly time logging dashboard
- `timelog catchup` — walk through missed days
- `timelog vacation` — register vacation ahead of time
- `timelog skip` — mark intentional no-log days
- `timelog auth login/logout/status` — GitHub auth management
- `timelog schedule install/uninstall/status` — scheduler management
- `timelog init` — first-time setup and health check
- Global install via pipx + `install.ps1` one-liner
