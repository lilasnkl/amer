# Amer — easy, safe git for team projects

Slash commands that handle the whole GitHub routine: get the team's latest work, commit cleanly,
check everything, push, and open the pull request. Your work never gets mixed up with anyone else's.
Works in **Claude Code**, **omp** and **Antigravity**, in any fork-based project
(`origin` = your fork, `upstream` = the team repo). Also works with a single shared repo.

## Install (every teammate, once)

**You need:** Git, Python 3.8+, and at least one of Claude Code, omp or Antigravity.
GitHub CLI (`gh`) is optional but recommended, so pull requests get created automatically.

1. Get it somewhere permanent (Claude Code reads updates from this folder, so don't leave it in Downloads):
   ```bash
   git clone https://github.com/lilasnkl/amer.git
   ```
   or download the zip from [Releases](https://github.com/lilasnkl/amer/releases) and unzip it.
2. Install:
   - **Windows:** double-click **`install.cmd`**
   - **macOS / Linux:** `sh install.sh`
   - or any terminal: `python install.py`
3. Restart your AI app(s).
4. Open your project and type **`/amer-setup`** (once per project). Then use **`/amer <task>`**.

The installer only touches the tools it finds on your computer:
- engine → `~/.teamflow/flow.py` (Python standard library only, nothing else to install)
- Claude Code → plugin `amer@amer-tools` (local marketplace = this folder)
- omp → `~/.omp/agent/commands/amer*.md`
- Antigravity → `~/.gemini/config/plugins/amer/` (skills = slash commands)

Options: `--only claude,omp,antigravity` forces specific tools. `--uninstall` removes everything.

**Claude Code only?** Two commands inside Claude Code, no install script needed:
```
/plugin marketplace add https://github.com/lilasnkl/amer.git
/plugin install amer@amer-tools
```
The engine (`~/.teamflow/flow.py`) is set up on first use: if it's missing, the command copies it from
the plugin. For omp and Antigravity, run `install.cmd` / `install.sh` from a clone.
(omp and Antigravity still need `install.cmd` / `install.sh` from a clone.)

## Update
`git pull` in the folder (or unzip the new release over it), then run the installer again and restart the app.
The installed version is printed by the installer and shown in Claude Code under `/plugin`.

## البداية السريعة (عربي)
1. حط المجلد بمكان ثابت (مش بالتنزيلات)، وبعدين دبل كليك على **`install.cmd`** (ويندوز) أو `sh install.sh` (ماك ولينكس).
2. سكّر برنامج الذكاء الاصطناعي وافتحه من جديد (Claude أو omp أو Antigravity).
3. افتح المشروع واكتب **`/amer-setup`** (مرة وحدة بس لكل مشروع).
4. بعد هيك لأي مهمة: **`/amer <المهمة>`**. الوكيل بينفّذها وبيرفعها وبيفتح طلب الدمج (PR)، وبيسألك مرة وحدة قبل الإرسال.
   - `yes` بآخر الأمر: بيرسل بدون سؤال.
   - `draft` بآخر الأمر: بيفتح الطلب كمسودة.
5. لتحديث الأداة: حط النسخة الجديدة مكان القديمة، وشغّل `install.cmd` مرة تانية.

## Commands

| Command | Use it when |
|---|---|
| **`/amer <task> [yes] [draft]`** | **Task in, pull request out:** sync with the team → understand and implement the task (with tests) → self-test → clean commits → sync again and bump the version → checks and fixes → verify the PR holds only your work → push → PR → report. It asks once before sending, or not at all with `yes`. With no task, it ships the work in progress. Example: `/amer add a "Create MO" button on the project form` |
| `/amer-setup` | Once per project. Detects where PRs go (e.g. `you:your-branch → team:base-branch`). |
| `/amer-start [name]` | Start of the day: bring in the team's latest work. With a name, it makes a fresh branch for a separate task. |
| `/amer-status` | "Where am I?": branch, new team commits, unsaved or unpushed work, versions, open PRs. |
| `/amer-save [hint]` | Commit: picks the right files, keeps junk out, bumps the Odoo version, writes a `type(scope): … vX` message. |
| `/amer-check` | Pre-flight checks (see below). |
| `/amer-ship` | Save → sync → check → verify the PR holds only your work → push → open or update the PR. |
| `/amer-undo` | Safe undo for common mistakes. Never loses work and never rewrites pushed history. |
| `/amer-help` | The routine and the rules. |

In Claude Code they also appear as `/amer:amer-start` etc. In omp, skills are also listed as `/skill:amer-*`.

## What `/amer-check` verifies
- Python, XML, JS (via node), JSON and CSV syntax of changed files
- Odoo manifests: listed data files exist, and new view/data/security files are actually listed
- Module version bumped when code changed, never lower than the team's, and migration folders match
- No `__pycache__`/`.pyc`/zip/log/`.env` files, leftover conflict markers, or obvious secrets
- Debug leftovers (`print(`, `pdb`, `console.log`, `debugger`) in added lines
- Commit messages follow `type(scope): summary`, and no other person's commits slip into the PR
- **Conflict preview** against the team's latest (`git merge-tree`, which doesn't touch your files)
  plus a list of files a teammate also changed
- Optional `--odoo`: real Odoo tests for the changed modules, if `odoo` is configured in `.git/teamflow.json`

## Safety built in
- Settings live in `.git/teamflow.json` and are never committed. This plugin folder lives outside the
  project, so it can't leak into commits.
- Refuses to push to the shared base branch, `main` or `master`. Never force-pushes. Undo refuses to
  rewrite commits that are already on GitHub.
- Enables `rerere` so git remembers how a conflict was resolved, and `zdiff3` for clearer conflicts.
- Pull requests: uses `gh` if it's installed and logged in. Otherwise it opens the browser on a
  pre-filled "Create pull request" page.
  For full automation: `winget install --id GitHub.cli` then `gh auth login`.

## Releasing a new version (maintainers)
1. Edit the skills in `plugin/skills/` or the engine in `plugin/scripts/flow.py`.
2. **Bump `version` in `plugin/.claude-plugin/plugin.json`.** Claude Code only refreshes a plugin
   when its version changes. Add a line to `CHANGELOG.md`.
3. `python install.py` to test locally, then commit, `git tag vX.Y.Z`, push, and attach
   `git archive --format=zip --prefix=amer/ -o dist/amer-vX.Y.Z.zip vX.Y.Z` to a GitHub release.

## Engine directly (any terminal)
```bash
python ~/.teamflow/flow.py status | sync [--new NAME] [--stash] | changes | check [--all] [--odoo] | bump MODULE | pr --title T --body-file F | undo-commit | doctor | setup [--write]
```
