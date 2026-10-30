---
name: amer-ship
description: Ship work for review - save any pending changes, sync with the team's latest, run checks, verify the PR contains only the user's own work, push, and open or update the pull request with a professional description.
disable-model-invocation: true
argument-hint: "[--draft]"
---

# Amer — ship (push + pull request)

Answer in the language the user writes in. Write PR titles and descriptions in **English**. Engine:
`python "$HOME/.teamflow/flow.py"` (try `python3` or `py` if `python` is missing). Never force-push
and never push to the team's base branch.

**If `$HOME/.teamflow/flow.py` is missing**, set it up first: copy `scripts/flow.py` from this plugin
(two folders up from this skill's base directory: `<skill dir>/../../scripts/flow.py`) to
`$HOME/.teamflow/flow.py`, creating the folder. If you can't find it, tell the user to run the Amer
installer (`install.cmd` on Windows, `sh install.sh` on macOS/Linux) and stop.

## 1. Save
`flow.py status`. If settings are not saved, do `/amer-setup` first. If there are uncommitted changes,
do the `/amer-save` steps first. Ask if some changes should stay out of this PR.

## 2. Sync
`flow.py sync`. On conflicts (exit 2) resolve them exactly as `/amer-start` describes, then continue.

## 3. Check
`flow.py check --no-fetch`. Stop on any ERROR: explain it, offer the fix, and re-run. Fix obvious WARNs.
If a module changed but its version was not bumped, bump it (`flow.py bump <module>`), commit
`chore(<scope>): bump version v<x>`, or amend only if that last commit was never pushed.

## 4. Make sure the PR contains only the user's work
Run `flow.py changes`. Confirm:
- every listed commit is the user's own and belongs to this task. A commit marked `<- by <someone>, not you`
  means stop and explain,
- no unrelated files. In `single` mode, if a previous PR from the same branch is still **open** (see
  `flow.py status` when `gh` is available), new commits will join that PR. Tell them, and suggest
  `/amer-start <name>` for a separate task.

## 5. Write the pull request
Title: a single commit uses its subject. Several commits get one summary in the same
`type(scope): summary vX` style.
Body (write it to a temp file, e.g. in the system temp folder, **not** inside the repo):
```
## Summary
<1-3 sentences: what and why, in business terms>

## Changes
- <module/area>: <change>
...

## Version / deploy notes
- <module>: <old> -> <new> (module upgrade runs on deploy)
- <migrations, new data/security files, settings to configure — or "none">

## How to test
1. <steps a reviewer can click through in Odoo>

## Checks
- Amer pre-flight: PASSED (<n> warnings: ...)
- Related automated tests: <tests/test_*.py files covering this area> (run on Odoo.sh)
```

## 6. Confirm, then send
Show the user the title, commits, files and target (`<fork_owner>:<branch> -> <upstream_repo>:<base>`)
and ask "Send it?". On yes:
`flow.py pr --title "<title>" --body-file "<file>"` (add `--draft` if asked: $ARGUMENTS).
- With `gh`, it creates the PR, or reports the already-open PR it updated.
- Without `gh`, it opens the browser on a pre-filled page. They only press **Create pull request**.
  Give them the link too.
- Exit 3 "GitHub has commits you don't have" → run `flow.py sync`, then ship again. Never force.

## 7. Report
Give the PR link (or the browser instructions) and the next steps: Odoo.sh builds and tests the branch,
the reviewer merges, then `/amer-start` brings the merge back. Delete the temp body file.
