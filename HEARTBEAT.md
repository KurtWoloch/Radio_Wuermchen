# HEARTBEAT.md

Chess and Moltbook are handled by dedicated Python scripts running as Windows Scheduled Tasks.
Do NOT duplicate their work with API calls.

- **OpenClawChessHeartbeat**: `chess_controller.py check` — every 10 min
- **MoltbookChecker**: `moltbook_checker.py check` — every 30 min

## What to check in heartbeats

### 1. Moltbook alerts
The Moltbook script writes `moltbook_alert.txt` (in workspace) when something needs attention.
- If `moltbook_alert.txt` exists → read it, act on the alerts (reply to comments, check DMs, etc.), then delete the file
- If it doesn't exist → nothing needs attention, move on
- Do NOT call the Moltbook API yourself — the script handles notification checking
- **Active participation** (browsing feed, commenting, posting) is handled by a separate cron job "Moltbook Active Participation" (runs 8:00 + 20:00 Vienna time, Gemini model, isolated session)

### 2. Chess
The chess script handles moves autonomously.
- Only check `chess_controller.py` output if Kurt asks about a game
- Do NOT make chess API calls in heartbeats

### 3. Any tasks listed below
(none)

## Rules
- If nothing needs attention → reply HEARTBEAT_OK immediately
- Do NOT generate analysis, commentary, or self-reflection
- Do NOT make API calls that duplicate scheduled task work
- Consult the actual Python scripts before changing this file
