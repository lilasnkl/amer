---
name: amer
description: Give the agent a task and it does everything, end to end - sync with the team, understand and implement the task in the code, test it, commit cleanly, bump the version, run checks, push, open the pull request, and report. Without a task it ships the work already in progress.
disable-model-invocation: true
argument-hint: "<the task to do> [yes] [draft]"
---

# Amer — GO: task in, pull request out

Answer in the language the user writes in. Write code, comments, commit messages, PR titles and PR
bodies in **English**. Engine: `python "$HOME/.teamflow/flow.py"` (try `python3` or `py` if `python` is
missing).

**If `$HOME/.teamflow/flow.py` is missing**, set it up first: copy `scripts/flow.py` from this plugin
(two folders up from this skill's base directory: `<skill dir>/../../scripts/flow.py`) to
`$HOME/.teamflow/flow.py`, creating the folder. If you can't find it, tell the user to run the Amer
installer (`install.cmd` on Windows, `sh install.sh` on macOS/Linux) and stop.

**The task:** `$ARGUMENTS`
- Words `yes` (skip the final confirmation) and `draft` (open the PR as a draft) are options. The rest is
  the task.
- **Task given:** do it fully (stages 1-11).
- **No task, but uncommitted changes exist:** skip stages 3-5 and ship that work.
- **No task and no changes:** ask "What should I do?", then continue with the answer.

Work **autonomously from start to finish**. Show a one-line progress note per stage
(e.g. `4/11 Implementing…`). Only stop to ask when:
- the task is genuinely ambiguous, and a wrong guess would change business behaviour (ask at most once,
  with your proposed interpretation),
- two conflicting changes really contradict each other,
- an ERROR can't be fixed safely,
- or at the final confirmation in stage 10 (skipped with `yes`).

**Never** run `git reset --hard`, `git clean`, `git push --force` or `git checkout -- .`, and never delete
branches. Never push to the team's base branch or main/master. Never edit Odoo core or enterprise code.

## 1/11 Ready?
- `flow.py doctor`. If the config is NOT SET UP, run `flow.py setup`, then `flow.py setup --write` (ask only
  if the detected target looks wrong).
- `flow.py status`. If a merge or rebase is in progress, finish it (stage 2 rules) or ask. If they are on a
  shared branch (base/main), create a task branch with `flow.py sync --new "<short-task-name>"`.

## 2/11 Start from the team's latest code
- If there are uncommitted changes from before:
  - they belong to this task: keep them and use `flow.py sync --stash`,
  - they are unrelated: commit them separately first (stage 6 rules), then sync,
  - unsure: ask.
- If the config `mode` is `feature`: `flow.py sync --new "<short-task-name>"`. Otherwise: `flow.py sync`.
- Exit 0 means continue. Exit 3 means read the STOP message and fix or ask. Exit 2 means conflicts:
  - For each file, read it and `git log --oneline -3 MERGE_HEAD -- <file>` to see what the teammate meant.
  - Keep **both** intentions; never drop the teammate's change.
    - `__manifest__.py` version: the higher one.
    - `__manifest__.py` data list: union of both, security files first.
    - `ir.model.access.csv`: all lines, with unique ids.
    - XML: keep both, valid, with unique record ids.
    - Python: merge the logic, and ask only if the changes truly contradict.
  - `git add <files>`, `git commit --no-edit`, then sync again until it exits 0.
- Note any **Revert** commits flagged in the sync output for the final report.

## 3/11 Understand the task
- Find the code involved: search models, views, wizards, reports, security and tests for the feature's
  names and fields. Read the closest existing implementation of something similar and copy its patterns.
- Read the module's `__manifest__.py` (dependencies, data order) and the related `tests/test_*.py`.
- Write a short plan for yourself: which files change, and what the user will see. If the task is
  ambiguous in a way that matters, ask now (once).

## 4/11 Implement
Follow the project's existing style exactly: naming, comment density, Odoo 19 idioms, and how
neighbouring code does things.
- **Models:** fields with `string`/`help` like their neighbours, `@api.depends` on computes, no business
  logic hidden in views. Keep `create`/`write` overrides minimal and call `super()`.
- **Views:** inherit with precise xpaths. Use Odoo 19 syntax (`invisible="..."` expressions, `<list>`).
  Keep the existing UI patterns.
- **New model** → add access rules to `security/ir.model.access.csv`. **New XML/CSV file** → add it to
  the manifest `data` in the right order.
- **Data changes on existing records** → add a migration in `migrations/<new version>/` only if the module
  already uses that pattern for similar changes.
- **Tests:** if the area has tests in `tests/`, add or extend a test for the new behaviour in the same
  style (same base class, same tags), and register new test files in `tests/__init__.py`.
- Keep the change focused on the task. Don't touch unrelated code.

## 5/11 Self-test
- `flow.py check --no-fetch`, and if the `odoo` block in `.git/teamflow.json` is configured,
  `flow.py check --no-fetch --odoo`.
- Re-read your own diff (`git diff`) like a reviewer would: logic errors, missing fields in views,
  wrong xpaths, access rights, translations of user-facing strings in the module's style, and edge cases
  (empty records, multi-company, currency).
- Fix and repeat until there are 0 errors and no WARNs caused by your change.

## 6/11 Commit cleanly
- Stage explicit paths only (never `git add -A` / `.`), and never stage `__pycache__/`, `*.pyc`, zips,
  logs, `.env` or dumps.
- One commit per logical change, usually one for the task.
- Message: `type(scope): short imperative summary`, lowercase, no period. Types are feat, fix, refactor,
  perf, style, test, docs, chore. Team scopes are sales, invoice, advance, mrp, project_mrp, views, wizard,
  purchase, stock and crm. Add a bullet body when the why isn't obvious.

## 7/11 Sync again and bump the version
- `flow.py sync`, because teammates may have pushed while you worked. Resolve conflicts with the stage 2 rules.
- For each Odoo module changed (models, views, data, security, wizards, reports or migrations, not only
  tests/docs/static): `flow.py bump <module>`. It goes above both their version and the team's, and does
  nothing if already bumped. Then:
  - if HEAD is their own **non-merge**, **unpushed** commit (`git rev-list --parents -n 1 HEAD` shows one
    parent and `git branch -r --contains HEAD` prints nothing): `git add <module>/__manifest__.py` and
    `git commit --amend -m "<same subject> v<version>"`, keeping any body,
  - otherwise commit `chore(<scope>): bump version v<version>`.
- If you added `migrations/<version>/`, its folder name must equal the new manifest version.

## 8/11 Final checks
`flow.py check --no-fetch` must show 0 errors. Fix and commit (amend if unpushed) until it does. If it
shows `will conflict` / `out of date`, go back to stage 7. If an ERROR can't be fixed safely, STOP,
explain it, and ask.

## 9/11 Make sure the PR contains only the user's work
`flow.py changes` (and `flow.py status` for open PRs when `gh` works):
- Every commit must be the user's own and belong to this work. Any `<- by <someone>, not you` means STOP and explain.
- No unrelated files.
- In `single` mode, if a PR from this branch is already **open**, the new commits will join it. Say so.

## 10/11 Write and send the pull request
- **Title:** one commit uses its subject. Several commits get one `type(scope): summary vX` line.
- **Body:** write it to a temp file **outside the repo** (system temp folder):
```
## Summary
<the task, and what was done and why, in business terms>

## Changes
- <module/area>: <change>

## Version / deploy notes
- <module>: <old> -> <new> (module upgrade runs on deploy)
- <migrations, new data/security files, settings to configure — or "none">

## How to test
1. <steps a reviewer can click through in Odoo>

## Checks
- Amer pre-flight: PASSED (<n> warnings: ...)
- Automated tests: <tests added/changed, and related tests/test_*.py> (run on Odoo.sh)
```
- **Confirmation:** unless `yes` was given, show one compact summary: what was implemented (2-3 bullets),
  target (`<fork_owner>:<branch> → <upstream_repo>:<base>`), commits, files count, version, PR title, and
  whether it's a new or existing PR. Ask **"Send it?"** once. If they ask for changes, make them, then go
  back to stage 5.
- **Send:** `flow.py pr --title "<title>" --body-file "<file>"`, plus `--draft` if requested.
  - Exit 3 "GitHub has commits you don't have" means run `flow.py sync` and send again. Never force.
  - Without `gh`, a pre-filled browser page opens and they press **Create pull request**.
- Delete the temp body file.

## 11/11 Report
- ✅ what was implemented (plain words) and the files changed
- ✅ commits, version change, and conflicts resolved (if any) and how
- ✅ checks result, and the tests added
- 🔗 PR link (or browser instructions). If `gh` works, run `gh pr checks <url>` once (no polling).
- ⚠️ anything to verify by hand in Odoo, and any Revert noted in stage 2
- **Next:** Odoo.sh builds and tests the branch, and the reviewer merges. For the next task:
  `/amer <task>`.
