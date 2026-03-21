# SAP Time Registration

This file maps your projects and meetings to SAP accounts and activity codes.
The AI assistant reads this file to automatically categorize your Outlook calendar events.
Add keywords, aliases, and context to help it make better decisions over time.

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `python -m timelog log` | Log today (Outlook → AI → SAP) |
| `python -m timelog status` | See this week's logging status |
| `python -m timelog catchup` | Catch up on missed days |
| `python -m timelog vacation 2026-03-25 2026-03-29` | Register vacation |
| `python -m timelog skip` | Mark today as no-log day |
| `python -m timelog daemon install` | Set up daily reminders |

---

## Activity Codes

| Code | Name            | Description                                              |
|------|-----------------|----------------------------------------------------------|
| D100 | Development     | Coding, code reviews, technical design, debugging       |
| M200 | Meetings        | Project meetings, standups, demos, planning sessions    |
| A300 | Analysis        | Research, documentation, requirements gathering         |
| O400 | Operations      | Deployments, incidents, support, maintenance            |
| T500 | Training        | Learning, courses, onboarding, conferences              |

---

## Accounts

### PROJ-1000 · My Main Project
- **SAP Account Code:** PROJ-1000
- **Default Activity:** D100
- **Keywords:** main project, feature, sprint, backend, frontend, api
- **Aliases:** project alpha, alpha
- **Notes:** Core development work. Use D100 for dev tasks, M200 for project meetings.

### PROJ-1001 · Another Project
- **SAP Account Code:** PROJ-1001
- **Default Activity:** D100
- **Keywords:** project beta, beta, integration, migration
- **Aliases:** beta
- **Notes:** Secondary project. Flag unclear entries.

### INTERNAL · Internal / General
- **SAP Account Code:** INTERNAL
- **Default Activity:** M200
- **Keywords:** 1:1, one on one, all hands, team meeting, company meeting, internal, admin, planning
- **Aliases:** internal, overhead
- **Notes:** Catch-all for internal meetings, HR, admin work.

### TRAINING · Training & Development
- **SAP Account Code:** TRAINING
- **Default Activity:** T500
- **Keywords:** course, learning, training, conference, workshop, onboarding
- **Aliases:** learning
- **Notes:** Self-improvement and formal training.

---

## Mapping Rules (populated automatically by the AI assistant)

<!-- The tool appends learned mappings here when you confirm a new mapping -->
<!-- Format: "Event keyword/pattern" → Account | Activity -->
