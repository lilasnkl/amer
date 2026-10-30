---
name: amer-status
description: Show where the user stands in git - current branch, new team commits not yet pulled, unpushed commits, uncommitted files, module versions vs team, open pull requests - and suggest the next /amer command.
argument-hint: ""
---

# Amer — status

Answer in the language the user writes in. Engine: `python "$HOME/.teamflow/flow.py"` (try `python3`
or `py` if `python` is missing).

**If `$HOME/.teamflow/flow.py` is missing**, set it up first: copy `scripts/flow.py` from this plugin
(two folders up from this skill's base directory: `<skill dir>/../../scripts/flow.py`) to
`$HOME/.teamflow/flow.py`, creating the folder. If you can't find it, tell the user to run the Amer
installer (`install.cmd` on Windows, `sh install.sh` on macOS/Linux) and stop.

Run `flow.py status` and turn it into a short, friendly dashboard:
- **Branch**: name, and a warning if it's a shared branch.
- **Team**: how many new team commits they don't have yet → suggest `/amer-start`.
- **Mine**: commits not pushed, files not committed → suggest `/amer-save` / `/amer-ship`.
- **Versions**: modules where their version differs from the team's.
- **Pull requests**: open PRs from this branch (only when `gh` is set up).
- Any merge or rebase in progress → explain and offer help to finish or cancel it.

End with exactly one recommended next command.
