---
name: amer-check
description: Run Amer pre-flight checks on the current branch - Python/XML/JS/CSV syntax, Odoo manifest and version rules, junk files, debug code, commit messages, and conflicts/overlap with teammates' latest work - and offer fixes.
argument-hint: "[--all | --odoo]"
---

# Amer — check

Answer in the language the user writes in. Engine: `python "$HOME/.teamflow/flow.py"` (try `python3`
or `py` if `python` is missing).

**If `$HOME/.teamflow/flow.py` is missing**, set it up first: copy `scripts/flow.py` from this plugin
(two folders up from this skill's base directory: `<skill dir>/../../scripts/flow.py`) to
`$HOME/.teamflow/flow.py`, creating the folder. If you can't find it, tell the user to run the Amer
installer (`install.cmd` on Windows, `sh install.sh` on macOS/Linux) and stop.

1. Run `flow.py check $ARGUMENTS`. `--all` checks every file. `--odoo` also runs the module's real
   Odoo tests if a local Odoo is configured in `.git/teamflow.json`.
2. Explain the results grouped as **must fix** (ERROR), **should fix** (WARN), **for info** (INFO).
   Give one plain line per item: what it means and how to fix it.
   - `will conflict` / `out of date` → run `/amer-start` first.
   - `version` → `/amer-save` will bump it (or `flow.py bump <module>`).
   - `manifest ... not in the manifest data list` → add the file to `data` in `__manifest__.py`, or
     confirm it is intentionally not loaded.
   - `commits ... by <someone>, not you` → the PR would carry someone else's commits. Usually their branch
     is missing a sync, or they branched from the wrong place. Help them fix it before shipping.
   - `odoo tests not run locally` is normal. Odoo.sh runs the real tests after the push.
3. Offer to fix the clear-cut items now (syntax errors, debug prints, missing manifest entries, junk
   files). Ask before anything that changes behaviour.
4. If changed Python files have a matching `tests/test_*.py`, point out which test files cover the
   change, so they know what Odoo.sh will exercise.
