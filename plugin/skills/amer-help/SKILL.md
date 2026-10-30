---
name: amer-help
description: Explain the Amer commands and the daily git routine (start, save, check, ship). Use when the user asks how to work with git/GitHub in this project, what to do next, or which /amer command to use.
argument-hint: "[question]"
---

# Amer — help

Answer in the language the user writes in. Keep it short and friendly. If the user asked a specific
question ($ARGUMENTS), answer that first, then show the routine only if useful.

Run `python "$HOME/.teamflow/flow.py" doctor` (try `python3` or `py` if `python` is missing) and
mention anything it says needs attention.

**If `$HOME/.teamflow/flow.py` is missing**, set it up first: copy `scripts/flow.py` from this plugin
(two folders up from this skill's base directory: `<skill dir>/../../scripts/flow.py`) to
`$HOME/.teamflow/flow.py`, creating the folder. If you can't find it, tell the user to run the Amer
installer (`install.cmd` on Windows, `sh install.sh` on macOS/Linux) and stop.

## The daily routine

**Easiest: `/amer <task>`.** Describe the task and the agent does everything: gets the team's
latest, writes the code and tests, commits, bumps the version, checks, pushes and opens the pull request.
It asks once before sending (add `yes` to skip that question). With no task, it ships the work already
in progress.

| When | Command | What it does |
|---|---|---|
| Any task | `/amer <task> [yes] [draft]` | Task in, pull request out, A to Z. |
| Once per project | `/amer-setup` | Detects where pull requests go and saves it. |
| Start of the day / before new work | `/amer-start` | Brings in the team's latest work and handles conflicts. |
| New separate task | `/amer-start <name>` | Fresh branch from the team's latest code, so each task gets its own clean PR. |
| Any time | `/amer-status` | Shows the current branch, what's new from the team, and anything not yet saved or pushed. |
| A piece of work is done | `/amer-save` | Picks the right files, bumps the version, writes a clean commit. |
| Before sending | `/amer-check` | Runs the safety checks: syntax, XML, manifest, version, conflicts, debug code. |
| Ready for review | `/amer-ship` | Syncs, checks, pushes, then opens or updates the pull request. |
| Made a mistake | `/amer-undo` | Safe undo options. Never loses work. |

## Golden rules (the plugin enforces them)
1. Always start with `/amer-start`, so you build on the team's latest code.
2. One task = one commit message that says what changed, e.g. `fix(sales): ...`.
3. Never commit `__pycache__`, `.pyc`, zips, logs, `.env`.
4. Bump the module version when models, views, data or security change (Odoo upgrades on deploy).
5. Never force-push and never `reset --hard` shared work.
6. The pull request shows only your own changes. `/amer-ship` checks this before sending.
