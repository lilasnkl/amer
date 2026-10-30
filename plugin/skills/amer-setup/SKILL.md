---
name: amer-setup
description: One-time Amer setup for the current git project - detects the fork/upstream remotes and the branch pull requests go into, saves it inside .git, and checks tools (git, python, gh).
disable-model-invocation: true
argument-hint: "[base-branch]"
---

# Amer — setup this project

Answer in the language the user writes in. Engine: `python "$HOME/.teamflow/flow.py"` (try `python3`
or `py` if `python` is missing).

**If `$HOME/.teamflow/flow.py` is missing**, set it up first: copy `scripts/flow.py` from this plugin
(two folders up from this skill's base directory: `<skill dir>/../../scripts/flow.py`) to
`$HOME/.teamflow/flow.py`, creating the folder. If you can't find it, tell the user to run the Amer
installer (`install.cmd` on Windows, `sh install.sh` on macOS/Linux) and stop.

1. Run `python "$HOME/.teamflow/flow.py" doctor` and `python "$HOME/.teamflow/flow.py" setup`.
   If the user gave a base branch ($ARGUMENTS), add `--base-branch <name>`.
2. Explain the detected plan in one short table: where their branch is pushed (fork remote), where
   pull requests go (upstream repo and base branch), their working branch, and why the base was chosen.
3. Ask the user to confirm, or to correct the base branch, working branch or mode:
   - `single`: keep working on one personal branch (e.g. their name), one PR at a time. This is the
     default and matches how the team works now.
   - `feature`: a new branch per task (`/amer-start <name>`). Several PRs can be open at once and none mix.
4. After confirmation run `setup --write` with any corrections (`--base-branch`, `--work-branch`,
   `--mode`, `--feature-prefix`). It saves `.git/teamflow.json` (never committed) and turns on
   `rerere` (git remembers conflict fixes), `fetch.prune` and `zdiff3` conflict view for this repo only.
5. If `gh` is missing or not logged in, explain that pull requests will open in the browser
   pre-filled (one click). Full automation needs `winget install --id GitHub.cli` and then
   `gh auth login`. Let the user run these commands themselves.
6. Optional: if the user has a local Odoo, offer to fill the `odoo` block in `.git/teamflow.json`
   (`bin`: path to odoo-bin, `config`: odoo.conf, `database`: a test DB) so `/amer-check` can run
   real tests with `--odoo`.
7. Finish with: "Setup done. Next: `/amer-start`".
