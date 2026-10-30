---
name: amer-start
description: Start working - bring the team's latest commits into the current branch (or create a fresh task branch with a name), resolve conflicts safely, and summarize what teammates changed.
disable-model-invocation: true
argument-hint: "[new-task-name]"
---

# Amer — start / sync

Answer in the language the user writes in. Engine: `python "$HOME/.teamflow/flow.py"` (try `python3`
or `py` if `python` is missing). Never run `git reset --hard`, `git push --force`, `git clean`,
`git checkout -- .` or delete branches unless the user explicitly asks in this conversation.

**If `$HOME/.teamflow/flow.py` is missing**, set it up first: copy `scripts/flow.py` from this plugin
(two folders up from this skill's base directory: `<skill dir>/../../scripts/flow.py`) to
`$HOME/.teamflow/flow.py`, creating the folder. If you can't find it, tell the user to run the Amer
installer (`install.cmd` on Windows, `sh install.sh` on macOS/Linux) and stop.

## Steps
1. Run `flow.py status`. If it says settings are not saved, run the `/amer-setup` steps first.
2. If there are uncommitted changes, ask the user which they want:
   - **save them first**: do the `/amer-save` steps, then continue, or
   - **set them aside**: add `--stash` to the sync. They come back automatically after.
3. Run the sync:
   - New separate task (user gave a name: $ARGUMENTS): `flow.py sync --new "<name>"`. This creates a
     fresh branch from the team's latest code.
   - Otherwise: `flow.py sync`.
4. Exit code meanings: `0` done, `3` needs user action (explain the STOP message simply), `2` conflicts.

## If there are conflicts (exit code 2)
Nothing is lost. For each conflicted file:
1. Read the file and `git log --oneline -3 MERGE_HEAD -- <file>` to see what the teammate intended.
   Conflict blocks show `<<<<<<< ours` (their work), `||||||| base` (before both), `>>>>>>> theirs` (team).
2. Combine both intentions. Never drop the teammate's change just to make the conflict go away.
   Project rules:
   - `__manifest__.py` `version`: take the higher version. Later `/amer-save` bumps above the team.
   - `__manifest__.py` `data` list: keep every entry from both sides, with security files first.
   - `ir.model.access.csv`: keep all lines and make sure ids are unique.
   - XML views and records: keep both changes. Make sure the XML stays valid and record ids are unique.
   - Python: merge the logic. If the two changes really contradict each other, show both versions
     and ask the user.
3. Show the user a short summary of how each file was resolved, then `git add <files>` and
   `git commit --no-edit`.
4. Run `flow.py check --no-fetch` to confirm nothing is broken.
5. If the user wants to cancel: `git merge --abort`. Their branch goes back exactly as it was.

## Finish
Summarize in plain words:
- which teammates' changes came in (from the sync output), especially any file they are working on,
- any **Revert** commits flagged by the output. If one of their features was reverted on the team branch,
  explain that to ship it again they should re-apply it, not just push the old commit,
- the branch they are now on, and: "You're up to date. Work, then `/amer-save`."
