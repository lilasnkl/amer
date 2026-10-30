---
name: amer-save
description: Save work as a clean commit - review changes, keep unrelated or junk files out, bump the Odoo module version when needed, and write a conventional commit message in the team's style.
disable-model-invocation: true
argument-hint: "[what you did]"
---

# Amer — save (commit)

Answer in the language the user writes in, but write commit messages in **English**. Engine:
`python "$HOME/.teamflow/flow.py"` (try `python3` or `py` if `python` is missing).

**If `$HOME/.teamflow/flow.py` is missing**, set it up first: copy `scripts/flow.py` from this plugin
(two folders up from this skill's base directory: `<skill dir>/../../scripts/flow.py`) to
`$HOME/.teamflow/flow.py`, creating the folder. If you can't find it, tell the user to run the Amer
installer (`install.cmd` on Windows, `sh install.sh` on macOS/Linux) and stop.

## 1. Understand the change
- Run `git status --short` and `git diff` (plus `git diff --cached`), and `flow.py changes` for the
  team's commit style and module versions.
- The user's hint about the work: $ARGUMENTS

## 2. Choose files and keep commits separate
- Group the changed files by purpose. If they hold **two unrelated changes** (e.g. an invoice fix and
  an MRP feature), propose separate commits and ask.
- Never stage: `__pycache__/`, `*.pyc`, `.pytest_cache`, zips, logs, `.env`, editor folders, DB dumps,
  release notes or scratch files the user did not mean to share. Never use `git add -A` / `git add .`;
  stage explicit paths. If junk keeps appearing, offer to add it to `.gitignore`.
- If a file looks unrelated or accidental, ask before including it.

## 3. Run the quick checks
`flow.py check --no-fetch`. Fix ERRORs before committing (or explain them and ask). Fix WARNs that are
clearly mistakes: debug `print`, a new view file missing from the manifest `data` list.

## 4. Version bump (Odoo modules)
Bump when a module's models, views, data, security, wizards, reports or migrations changed. This is the
team convention, and Odoo.sh only upgrades a module when its version changes. Tests or docs alone: no bump.
- `flow.py bump <module_folder>`. It goes one step above both their version and the team's version, and
  does nothing if their branch is already bumped.
- If a `migrations/<version>/` folder was added, it must match the new manifest version.

## 5. Commit message (team style)
`type(scope): short imperative summary` + ` v<new version>` when bumped. Lowercase, no trailing period,
summary under ~90 chars. Types: feat, fix, refactor, perf, style, test, docs, chore.
Scopes the team uses: sales, invoice, advance, mrp, project_mrp, views, wizard, purchase, stock, crm.
Pick the closest one. Examples from this repo:
- `feat(project_mrp): add header button to create manufacturing orders from project v19.0.1.3.92`
- `fix(advance): calculate remaining advance amount based on available amount`
Add a body (blank line, then bullets) only when the why isn't obvious.

## 6. Commit
Show the user the file list and message. Then `git add <paths>` and `git commit -m "<subject>" [-m "<body>"]`.
Report: "Saved locally (not on GitHub yet). When ready: `/amer-ship`."
