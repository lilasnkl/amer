# Changelog

## 2.1.0 — team package
- Packaged for the whole team: `install.cmd` (Windows double-click), `install.sh` (macOS/Linux),
  and a README with English + Arabic quick start.
- The installer only installs into the AI tools it finds (Claude Code, omp, Antigravity) and checks
  for Python 3.8+ and git.
- Base-branch detection now also works for teammates without a fork or without merged PRs yet: it
  follows the branch where the team's pull requests are merged.
- Skill wording is neutral for any user.

## 2.0.0
- Renamed from TeamFlow (`/flow-*`) to Amer (`/amer`, `/amer-*`). The installer removes the old commands.

## 1.2.0
- `/amer <task>` (was `/flow-go`): the agent implements the task, then syncs, commits, bumps the version,
  checks, pushes and opens the PR.

## 1.0.0
- First release: setup, start, status, save, check, ship, undo, help and the `flow.py` engine.
