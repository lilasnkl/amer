---
name: amer-undo
description: Safely undo git mistakes without losing work - unstage files, undo the last unpushed commit, fix the last commit message, cancel a merge in progress, restore stashed work, or revert a pushed commit.
disable-model-invocation: true
argument-hint: "[what went wrong]"
---

# Amer — safe undo

Answer in the language the user writes in. Engine: `python "$HOME/.teamflow/flow.py"` (try `python3`
or `py` if `python` is missing).

**If `$HOME/.teamflow/flow.py` is missing**, set it up first: copy `scripts/flow.py` from this plugin
(two folders up from this skill's base directory: `<skill dir>/../../scripts/flow.py`) to
`$HOME/.teamflow/flow.py`, creating the folder. If you can't find it, tell the user to run the Amer
installer (`install.cmd` on Windows, `sh install.sh` on macOS/Linux) and stop.

First run `flow.py status` and `git log --oneline -5`. Understand what they want to undo ($ARGUMENTS).
If unclear, ask with these options:

| Situation | Safe action |
|---|---|
| Added a wrong file to the next commit | `git restore --staged <file>` (the file keeps its changes) |
| Last commit is wrong and **not pushed** | `flow.py undo-commit` (keeps the changes; refuses if already pushed) |
| Typo in the last commit message, **not pushed** | `git commit --amend -m "<new message>"` |
| A sync/merge went wrong and is still in progress | `git merge --abort` (back to exactly how it was) |
| Changes were set aside by a sync | `git stash list`, then `git stash pop` |
| A **pushed** commit must be cancelled | `git revert <sha>`, which makes a new commit that undoes it; then `/amer-ship` |
| Wants to throw away edits to a file | show `git diff <file>` first, **ask for explicit confirmation**, then `git restore <file>` |
| Lost a commit | `git reflog` to find it, then `git branch rescue-<name> <sha>` |

Rules: never use `git reset --hard`, `git clean`, `git push --force` or branch deletion unless they
explicitly asks after seeing exactly what would be lost. Pushed history is never rewritten. Use revert.
After acting, run `flow.py status` and confirm the result in one line.
