#!/usr/bin/env python3
"""Amer engine: safe, repeatable git + GitHub workflow for fork-based team repos.

Used by the /amer-* commands in Claude Code, omp and Antigravity. Standard library only.

    python flow.py doctor            check tools, remotes, auth
    python flow.py setup [--write]   detect remotes/base branch, save .git/teamflow.json
    python flow.py status            where am I, what is new, what is pending
    python flow.py sync [--new NAME] [--stash]
                                     bring teammates' latest work into the branch
    python flow.py changes           what this branch will put in a PR
    python flow.py check [--odoo]    pre-flight checks before commit/push
    python flow.py bump MODULE       bump module manifest version (above base)
    python flow.py pr --title T --body-file F [--draft] [--no-open]
                                     push and open/update the pull request
    python flow.py undo-commit       undo last commit if it was never pushed

Exit codes: 0 ok, 1 checks failed / error, 2 merge conflicts, 3 needs user action.
"""
import argparse
import ast
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import webbrowser
import xml.etree.ElementTree as ET
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

CONFIG_NAME = "teamflow.json"
PROTECTED = {"main", "master", "production", "prod"}
JUNK_PATTERNS = [
    r"(^|/)__pycache__/", r"\.py[cod]$", r"(^|/)\.pytest_cache/", r"\.orig$", r"\.rej$",
    r"(^|/)\.env$", r"\.DS_Store$", r"(^|/)Thumbs\.db$", r"\.(zip|rar|7z|bak|tmp|log)$",
    r"(^|/)node_modules/", r"(^|/)\.idea/", r"(^|/)\.vscode/", r"\.sqlite3?$", r"\.dump$",
]
DEBUG_PATTERNS = {
    ".py": [r"^\s*print\(", r"\bpdb\.set_trace\(", r"\bbreakpoint\(\)", r"import pdb", r"\bipdb\b"],
    ".js": [r"\bconsole\.log\(", r"^\s*debugger;?"],
}
SECRET_PATTERN = re.compile(
    r"(api[_-]?key|secret|passw(or)?d|token)\s*[=:]\s*['\"][^'\"]{8,}['\"]|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}",
    re.I,
)
CONFLICT_START = re.compile(r"^<{7}( |$)", re.M)
CONFLICT_END = re.compile(r"^>{7}( |$)", re.M)
VERSION_RE = re.compile(r"""(["']version["']\s*:\s*["'])([^"']+)(["'])""")
CONVENTIONAL_RE = re.compile(r"^(feat|fix|refactor|perf|style|docs|test|chore|build|ci|revert)(\([\w./-]+\))?!?: .+|^Revert \"|^Merge ")


# ----------------------------------------------------------------------------- helpers

class FlowError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


def run(cmd, check=True, cwd=None, env=None):
    proc = subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if check and proc.returncode != 0:
        raise FlowError(f"command failed: {' '.join(cmd)}\n{proc.stderr.strip() or proc.stdout.strip()}")
    return proc


def git(*args, check=True):
    return run(["git", "-c", "core.quotepath=off", *args], check=check).stdout.strip()


def git_ok(*args):
    return run(["git", "-c", "core.quotepath=off", *args], check=False).returncode == 0


def lines(text):
    return [line for line in text.splitlines() if line.strip()]


def say(text=""):
    print(text)


def section(title):
    say()
    say(f"== {title} ==")


def repo_root():
    proc = run(["git", "rev-parse", "--show-toplevel"], check=False)
    if proc.returncode != 0:
        raise FlowError("Not inside a git repository. Open the project folder first.", 3)
    return Path(proc.stdout.strip())


def config_path():
    common = Path(git("rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = Path.cwd() / common
    return common / CONFIG_NAME


def load_config(required=True):
    path = config_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if required:
        detected = detect_config(do_fetch=False)
        detected["_unsaved"] = True
        return detected
    return None


def parse_github(url):
    match = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", url or "")
    return (match.group(1), match.group(2)) if match else (None, None)


def remotes():
    result = {}
    for name in lines(git("remote")):
        result[name] = git("remote", "get-url", name)
    return result


def current_branch():
    branch = git("branch", "--show-current")
    if not branch:
        raise FlowError("You are in 'detached HEAD' state (not on a branch). Ask the AI to help you get back on your branch.", 3)
    return branch


def ref_exists(ref):
    return git_ok("rev-parse", "--verify", "--quiet", ref)


def base_ref(cfg):
    return f"{cfg['upstream_remote']}/{cfg['base_branch']}"


def fetch(cfg, quiet=True):
    seen = []
    for remote in (cfg["upstream_remote"], cfg["fork_remote"]):
        if remote in seen:
            continue
        seen.append(remote)
        proc = run(["git", "fetch", "--prune", remote], check=False)
        if proc.returncode != 0:
            say(f"! could not fetch '{remote}': {proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else 'unknown error'}")
        elif not quiet:
            say(f"fetched {remote}")


def in_progress_operation():
    gitdir = Path(git("rev-parse", "--git-dir"))
    if not gitdir.is_absolute():
        gitdir = Path.cwd() / gitdir
    for marker, name in (("MERGE_HEAD", "merge"), ("rebase-merge", "rebase"), ("rebase-apply", "rebase"),
                         ("CHERRY_PICK_HEAD", "cherry-pick"), ("REVERT_HEAD", "revert")):
        if (gitdir / marker).exists():
            return name
    return None


def dirty_files():
    out = git("status", "--porcelain=v1", "--untracked-files=all")
    return [line for line in out.splitlines() if line.strip()]


def conflicted_files():
    return lines(git("diff", "--name-only", "--diff-filter=U"))


def ahead_behind(left, right):
    if not (ref_exists(left) and ref_exists(right)):
        return None
    out = git("rev-list", "--left-right", "--count", f"{left}...{right}")
    ahead, behind = out.split()
    return int(ahead), int(behind)


def user_email():
    return git("config", "user.email", check=False).lower()


def gh_ready():
    if not shutil.which("gh"):
        return False
    return run(["gh", "auth", "status"], check=False).returncode == 0


def manifest_version_text(text):
    match = VERSION_RE.search(text or "")
    return match.group(2) if match else None


def version_tuple(version):
    parts = []
    for part in (version or "").split("."):
        parts.append(int(part) if part.isdigit() else 0)
    return tuple(parts)


def module_of(path, root):
    """Top-most directory (inside the repo) that holds a __manifest__.py for this file."""
    parts = Path(path).parts
    for i in range(1, len(parts)):
        candidate = Path(*parts[:i])
        if (root / candidate / "__manifest__.py").exists():
            return candidate.as_posix()
    return None


def modules_in_repo(root):
    return sorted(p.parent.relative_to(root).as_posix() for p in root.glob("*/__manifest__.py"))


def version_at(ref, module):
    proc = run(["git", "show", f"{ref}:{module}/__manifest__.py"], check=False)
    return manifest_version_text(proc.stdout) if proc.returncode == 0 else None


def merge_base(cfg):
    ref = base_ref(cfg)
    if not ref_exists(ref):
        return None
    return git("merge-base", "HEAD", ref, check=False) or None


def branch_files(cfg):
    """Files this branch changes compared with the base (committed + uncommitted + untracked)."""
    mb = merge_base(cfg)
    files = set()
    if mb:
        files.update(lines(git("diff", "--name-only", mb)))
    files.update(lines(git("diff", "--name-only", "HEAD")))
    files.update(lines(git("ls-files", "--others", "--exclude-standard")))
    return sorted(files)


# ----------------------------------------------------------------------------- setup

def detect_config(do_fetch=True):
    rem = remotes()
    if not rem:
        raise FlowError("This repository has no remotes. Add the GitHub remote first.", 3)
    upstream = "upstream" if "upstream" in rem else ("origin" if "origin" in rem else next(iter(rem)))
    fork = "origin" if "origin" in rem else upstream
    up_owner, up_repo = parse_github(rem[upstream])
    fork_owner, fork_repo = parse_github(rem[fork])
    if do_fetch:
        for name in {upstream, fork}:
            run(["git", "fetch", "--prune", name], check=False)

    def latest_pr_branch(pattern):
        best, found = 0, None
        for ref in lines(git("for-each-ref", f"refs/remotes/{upstream}", "--format=%(refname:short)")):
            if ref.endswith("/HEAD") or ref == upstream:
                continue
            stamp = git("log", ref, "--first-parent", "--merges", "-n", "1", "-E",
                        f"--grep={pattern}", "--format=%ct", check=False)
            if stamp and int(stamp) > best:
                best, found = int(stamp), ref.split("/", 1)[1]
        return found

    base, reason = None, ""
    if fork_owner and fork != upstream:
        base = latest_pr_branch(f"^Merge pull request #[0-9]+ from {re.escape(fork_owner)}/")
        if base:
            reason = f"your latest merged pull request from '{fork_owner}' went into '{base}'"
    if not base:
        # teammates without a fork (or without merged PRs yet): follow where the team merges PRs
        base = latest_pr_branch("^Merge pull request #[0-9]+ from ")
        if base:
            reason = f"the team's most recent pull requests are merged into '{base}'"
    if not base:
        head = git("symbolic-ref", "--quiet", "--short", f"refs/remotes/{upstream}/HEAD", check=False)
        base = head.split("/", 1)[1] if head else "main"
        reason = f"default branch of '{upstream}'"

    branch = git("branch", "--show-current", check=False) or base
    name = (git("config", "user.name", check=False) or "dev").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-") or "dev"
    return {
        "upstream_remote": upstream,
        "fork_remote": fork,
        "upstream_repo": f"{up_owner}/{up_repo}" if up_owner else None,
        "fork_owner": fork_owner,
        "base_branch": base,
        "base_reason": reason,
        "mode": "single",
        "work_branch": branch,
        "feature_prefix": f"{slug}-",
        "commit_style": "conventional",
        "version_bump": "odoo-manifest" if modules_in_repo(repo_root()) else "none",
        "odoo": {"bin": "", "config": "", "database": ""},
    }


def cmd_setup(args):
    path = config_path()
    existing = load_config(required=False) if path.exists() else None
    cfg = detect_config(do_fetch=not args.no_fetch)
    if existing:
        cfg.update({k: v for k, v in existing.items() if k not in ("base_reason",)})
    for key in ("base_branch", "upstream_remote", "fork_remote", "mode", "work_branch", "feature_prefix"):
        value = getattr(args, key, None)
        if value:
            cfg[key] = value
    if cfg["base_branch"] in (None, ""):
        raise FlowError("Could not detect the base branch. Pass --base-branch NAME.", 3)
    if not ref_exists(base_ref(cfg)):
        say(f"! warning: {base_ref(cfg)} does not exist (run git fetch or check the name)")

    section("Amer settings for this project")
    for key in ("upstream_repo", "upstream_remote", "fork_remote", "fork_owner", "base_branch", "mode",
                "work_branch", "feature_prefix", "version_bump"):
        say(f"  {key:16} {cfg.get(key)}")
    if cfg.get("base_reason"):
        say(f"  (base detected because {cfg['base_reason']})")
    say(f"  pull requests go: {cfg.get('fork_owner')}:<branch>  ->  {cfg.get('upstream_repo')}:{cfg['base_branch']}")

    if args.write:
        cfg.pop("base_reason", None)
        cfg.pop("_unsaved", None)
        path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        git("config", "rerere.enabled", "true")   # remember conflict resolutions
        git("config", "fetch.prune", "true")      # drop deleted remote branches
        git("config", "merge.conflictstyle", "zdiff3")  # show the common ancestor in conflicts
        say()
        say(f"saved -> {path}  (inside .git, never committed)")
        say("enabled for this repo: rerere.enabled, fetch.prune, merge.conflictstyle=zdiff3")
    else:
        say()
        say("Not saved yet. Re-run with --write to save these settings.")
    return 0


def cmd_doctor(args):
    problems = 0
    section("Tools")
    say(f"  git     {git('--version')}")
    say(f"  python  {sys.version.split()[0]}")
    if shutil.which("gh"):
        auth = run(["gh", "auth", "status"], check=False)
        say(f"  gh      installed, {'logged in' if auth.returncode == 0 else 'NOT logged in (run: gh auth login)'}")
    else:
        say("  gh      not installed -> pull requests open in the browser for one click "
            "(install for full automation: winget install --id GitHub.cli)")
    say(f"  node    {'available (JS syntax checks on)' if shutil.which('node') else 'not found (JS checks skipped)'}")

    section("Identity")
    name, email = git("config", "user.name", check=False), git("config", "user.email", check=False)
    say(f"  user    {name or 'MISSING'} <{email or 'MISSING'}>")
    if not (name and email):
        problems += 1

    section("Repository")
    say(f"  root    {repo_root()}")
    for remote, url in remotes().items():
        say(f"  remote  {remote:9} {url}")
    cfg = load_config(required=False)
    if cfg:
        say(f"  config  {config_path()}  (base: {cfg['base_branch']}, mode: {cfg['mode']})")
    else:
        say("  config  NOT SET UP -> run /amer-setup")
        problems += 1
    op = in_progress_operation()
    if op:
        say(f"  !! a {op} is in progress")
        problems += 1
    say()
    say("doctor: OK" if not problems else f"doctor: {problems} thing(s) need attention")
    return 0 if not problems else 3


# ----------------------------------------------------------------------------- status / sync

def cmd_status(args):
    cfg = load_config()
    if not args.no_fetch:
        fetch(cfg)
    branch = current_branch()
    base = base_ref(cfg)
    section("Where you are")
    say(f"  branch      {branch}")
    say(f"  PR target   {cfg.get('upstream_repo')} : {cfg['base_branch']}")
    if cfg.get("_unsaved"):
        say("  (settings auto-detected, not saved: run /amer-setup)")
    if branch == cfg["base_branch"] or branch in PROTECTED:
        say(f"  !! you are on '{branch}' (a shared branch). Start work with /amer-start <name> or switch to your branch.")

    op = in_progress_operation()
    if op:
        say(f"  !! a {op} is in progress. Conflicted files: {', '.join(conflicted_files()) or 'none left'}")

    ab = ahead_behind("HEAD", base)
    if ab:
        ahead, behind = ab
        say(f"  vs team     {ahead} commit(s) of yours not in {base}; {behind} new team commit(s) you don't have yet")
        if behind:
            say("              -> run /amer-start to bring them in")
    fork_ref = f"{cfg['fork_remote']}/{branch}"
    ab = ahead_behind("HEAD", fork_ref)
    if ab:
        say(f"  vs GitHub   {ab[0]} commit(s) not pushed; {ab[1]} on GitHub you don't have locally")
    else:
        say("  vs GitHub   branch not pushed yet")

    dirty = dirty_files()
    section(f"Uncommitted changes ({len(dirty)})")
    for line in dirty[:40]:
        say(f"  {line}")
    if len(dirty) > 40:
        say(f"  ... and {len(dirty) - 40} more")
    if not dirty:
        say("  none - working tree clean")
    stashes = lines(git("stash", "list"))
    if stashes:
        say(f"  note: {len(stashes)} stash(es) saved (git stash list)")

    root = repo_root()
    mods = modules_in_repo(root)
    if mods:
        section("Module versions (yours / team)")
        for mod in mods:
            say(f"  {mod:34} {version_at('HEAD', mod) or '-':14} {version_at(base, mod) or '-'}")

    if gh_ready() and cfg.get("upstream_repo"):
        section("Open pull requests from this branch")
        head = f"{cfg['fork_owner']}:{branch}" if cfg["fork_remote"] != cfg["upstream_remote"] else branch
        proc = run(["gh", "pr", "list", "--repo", cfg["upstream_repo"], "--head", branch, "--state", "open",
                    "--json", "number,title,url,headRepositoryOwner"], check=False)
        prs = json.loads(proc.stdout or "[]") if proc.returncode == 0 else []
        prs = [p for p in prs if not cfg.get("fork_owner") or p.get("headRepositoryOwner", {}).get("login") == cfg["fork_owner"]]
        for pr in prs:
            say(f"  #{pr['number']} {pr['title']}\n     {pr['url']}")
        if not prs:
            say(f"  none open for {head}")
    return 0


def cmd_sync(args):
    cfg = load_config()
    op = in_progress_operation()
    if op:
        files = conflicted_files()
        if files:
            raise FlowError(f"A {op} is still in progress with conflicts in: {', '.join(files)}\n"
                            "Resolve them first (the AI can help), then run sync again.", 2)
        raise FlowError(f"A {op} is in progress. Finish it (git commit --no-edit) or abort it (git {op} --abort).", 3)

    stashed = False
    if dirty_files():
        if not args.stash:
            raise FlowError("You have uncommitted changes. Save them first (/amer-save) or re-run with --stash "
                            "to put them aside during the sync and restore them after.", 3)
        git("stash", "push", "--include-untracked", "-m", "teamflow: auto-stash before sync")
        stashed = True
        say("put your uncommitted changes aside (stash)")

    fetch(cfg, quiet=False)
    base = base_ref(cfg)
    if not ref_exists(base):
        raise FlowError(f"{base} not found. Check the base branch with /amer-setup.", 3)

    if args.new:
        name = re.sub(r"[^A-Za-z0-9._/-]+", "-", args.new).strip("-")
        branch = name if name.startswith(cfg["feature_prefix"]) else f"{cfg['feature_prefix']}{name}"
        if ref_exists(f"refs/heads/{branch}"):
            raise FlowError(f"Branch '{branch}' already exists. Pick another name or switch to it.", 3)
        git("switch", "--no-track", "-c", branch, base)
        say(f"created '{branch}' from the team's latest {base} ({git('log', '-1', '--format=%h %s')})")
        if stashed:
            restore_stash()
        return 0

    branch = current_branch()
    if branch == cfg["base_branch"] or branch in PROTECTED:
        raise FlowError(f"You are on '{branch}', a shared branch. Switch to your own branch "
                        f"(git switch {cfg['work_branch']}) or create one with /amer-start <name>.", 3)

    before = git("rev-parse", "HEAD")
    fork_ref = f"{cfg['fork_remote']}/{branch}"
    if ref_exists(fork_ref):
        ahead, behind = ahead_behind("HEAD", fork_ref)
        if behind:
            say(f"GitHub has {behind} commit(s) on '{branch}' you don't have locally - bringing them in")
            if not merge(fork_ref):
                return conflict_exit(stashed)

    incoming = lines(git("log", "--no-merges", "--format=%h|%an|%s", f"HEAD..{base}"))
    if not incoming and ahead_behind("HEAD", base)[1] == 0:
        say(f"already up to date with {base}")
    else:
        section(f"New team work coming from {base}")
        for entry in incoming[:30]:
            sha, author, subject = entry.split("|", 2)
            say(f"  {sha} {author:18} {subject}")
            if subject.startswith("Revert "):
                say("        ^ a REVERT: something was undone on the team branch - check it is not your feature")
        if len(incoming) > 30:
            say(f"  ... and {len(incoming) - 30} more")
        if not merge(base):
            return conflict_exit(stashed)

    after = git("rev-parse", "HEAD")
    if before != after:
        changed = lines(git("diff", "--stat", "--stat-width=100", before, after))
        section("Files updated by the sync")
        for line in changed[-25:]:
            say(f"  {line}")
    if stashed:
        restore_stash()
    say()
    say(f"sync done: '{branch}' now contains the team's latest work.")
    return 0


def merge(ref):
    proc = run(["git", "merge", "--no-edit", ref], check=False)
    if proc.returncode == 0:
        return True
    if conflicted_files():
        return False
    raise FlowError(f"merge of {ref} failed:\n{proc.stderr.strip() or proc.stdout.strip()}")


def conflict_exit(stashed):
    files = conflicted_files()
    section("CONFLICTS - same lines changed by you and a teammate")
    for f in files:
        say(f"  {f}")
    say()
    say("Nothing is lost. Resolve each file (keep both intentions), then:")
    say("  git add <file> ...   and   git commit --no-edit")
    say("To cancel the whole sync instead:  git merge --abort")
    if stashed:
        say("Your uncommitted work is safe in the stash; restore it after: git stash pop")
    return 2


def restore_stash():
    proc = run(["git", "stash", "pop"], check=False)
    if proc.returncode == 0:
        say("restored your uncommitted changes")
    else:
        say("! your stashed changes overlap the new code. They are still saved; "
            "resolve the conflicts shown by 'git status' (the AI can help), then run 'git stash drop'.")


# ----------------------------------------------------------------------------- changes

def cmd_changes(args):
    cfg = load_config()
    base = base_ref(cfg)
    branch = current_branch()
    me = user_email()
    section(f"What '{branch}' will bring into {base}")
    commits = lines(git("log", "--no-merges", "--format=%h|%ae|%an|%s", f"{base}..HEAD")) if ref_exists(base) else []
    if commits:
        say(f"  {len(commits)} commit(s):")
        for entry in commits:
            sha, email, author, subject = entry.split("|", 3)
            flag = "" if email.lower() == me else f"   <- by {author}, not you"
            say(f"    {sha} {subject}{flag}")
    else:
        say("  no commits yet that the team doesn't have")
    files = branch_files(cfg)
    root = repo_root()
    if files:
        groups = {}
        for f in files:
            groups.setdefault(module_of(f, root) or "(repo root)", []).append(f)
        say(f"  {len(files)} file(s) changed (committed + uncommitted):")
        for mod, fs in sorted(groups.items()):
            say(f"    [{mod}]")
            for f in fs:
                say(f"      {f}")
        mb = merge_base(cfg)
        if mb:
            stat = lines(git("diff", "--shortstat", mb))
            if stat:
                say(f"  size: {stat[-1].strip()}")
        for mod in sorted(m for m in groups if m != "(repo root)"):
            mine, team = version_at("HEAD", mod), version_at(base, mod)
            working = manifest_version_text((root / mod / "__manifest__.py").read_text(encoding="utf-8", errors="replace"))
            say(f"  version {mod}: team {team} -> yours {working}" + ("  (not bumped)" if working == team else ""))
    say()
    say("Recent team commit style:")
    for subject in lines(git("log", "--no-merges", "-8", "--format=%s", base if ref_exists(base) else "HEAD")):
        say(f"  {subject}")
    return 0


# ----------------------------------------------------------------------------- check

class Report:
    def __init__(self):
        self.items = []

    def add(self, level, area, message):
        self.items.append((level, area, message))

    def count(self, level):
        return sum(1 for item in self.items if item[0] == level)


def cmd_check(args):
    cfg = load_config()
    root = repo_root()
    base = base_ref(cfg)
    report = Report()
    if not args.no_fetch:
        fetch(cfg)

    files = branch_files(cfg)
    if args.all:
        files = sorted(set(files) | set(lines(git("ls-files"))))
    existing = [f for f in files if (root / f).is_file()]
    tracked_or_new = set(lines(git("ls-files"))) | set(lines(git("ls-files", "--others", "--exclude-standard")))
    say(f"checking {len(existing)} changed file(s) against {base}")

    # 1. junk + secrets + conflict markers
    for f in existing:
        if f in tracked_or_new and any(re.search(p, f) for p in JUNK_PATTERNS):
            report.add("ERROR", "junk file", f"{f} should not be committed (add it to .gitignore / unstage it)")
    for f in existing:
        path = root / f
        if path.stat().st_size > 5 * 1024 * 1024:
            report.add("WARN", "large file", f"{f} is {path.stat().st_size // 1024 // 1024} MB")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if CONFLICT_START.search(text) and CONFLICT_END.search(text):
            report.add("ERROR", "conflict", f"{f} still contains <<<<<<< / >>>>>>> conflict markers")
        if SECRET_PATTERN.search(text) and not f.endswith((".md", ".po", ".pot")):
            report.add("WARN", "secret?", f"{f} may contain a password/token - double check")

    # 2. syntax
    node = shutil.which("node")
    for f in existing:
        path = root / f
        if f.endswith(".py"):
            try:
                compile(path.read_text(encoding="utf-8", errors="replace"), f, "exec")
            except SyntaxError as exc:
                report.add("ERROR", "python", f"{f}:{exc.lineno}: {exc.msg}")
        elif f.endswith(".xml"):
            try:
                ET.parse(path)
            except ET.ParseError as exc:
                report.add("ERROR", "xml", f"{f}: {exc}")
        elif f.endswith(".csv"):
            check_csv(f, path, report)
        elif f.endswith(".js") and node and "/static/lib/" not in f:
            proc = run([node, "--check", str(path)], check=False)
            if proc.returncode != 0:
                detail = next((l for l in proc.stderr.splitlines() if "Error" in l), proc.stderr.strip()[:200])
                report.add("ERROR", "javascript", f"{f}: {detail}")
        elif f.endswith(".json"):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except ValueError as exc:
                report.add("ERROR", "json", f"{f}: {exc}")

    # 3. Odoo manifests
    touched = sorted({m for m in (module_of(f, root) for f in files) if m})
    for mod in touched:
        check_manifest(mod, root, files, base, cfg, report)

    # 4. debug leftovers in added lines
    mb = merge_base(cfg)
    if mb:
        diff = git("diff", "-U0", mb, "--", "*.py", "*.js", check=False)
        current = None
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                current = line[6:]
            elif line.startswith("+") and not line.startswith("+++") and current:
                ext = os.path.splitext(current)[1]
                if "/tests/" in current or current.startswith(("scripts/", "tests/")):
                    continue
                for pat in DEBUG_PATTERNS.get(ext, []):
                    if re.search(pat, line[1:]):
                        report.add("WARN", "debug code", f"{current}: {line[1:].strip()[:90]}")

    # 5. commits hygiene
    if ref_exists(base):
        me = user_email()
        for entry in lines(git("log", "--no-merges", "--format=%h|%ae|%an|%s", f"{base}..HEAD")):
            sha, email, author, subject = entry.split("|", 3)
            if email.lower() != me:
                report.add("WARN", "commits", f"{sha} by {author} will be in your PR: {subject}")
            if cfg.get("commit_style") == "conventional" and not CONVENTIONAL_RE.match(subject):
                report.add("WARN", "commits", f"{sha} message is not 'type(scope): summary': {subject}")
            if re.match(r"(?i)^(wip|fixup!|squash!|tmp|test commit)", subject):
                report.add("WARN", "commits", f"{sha} looks temporary: {subject}")

    # 6. conflicts / overlap with teammates
    if ref_exists(base):
        proc = run(["git", "merge-tree", "--write-tree", "--name-only", "--no-messages", "HEAD", base], check=False)
        if proc.returncode == 1:
            conflicts = lines(proc.stdout)[1:]
            report.add("ERROR", "will conflict",
                       f"your branch conflicts with the team's latest in: {', '.join(conflicts)} -> run /amer-start")
        elif mb:
            team_files = set(lines(git("diff", "--name-only", mb, base)))
            overlap = sorted(team_files & set(files))
            behind = ahead_behind("HEAD", base)[1]
            if behind:
                report.add("WARN", "out of date", f"{behind} team commit(s) not in your branch yet -> run /amer-start")
            for f in overlap:
                who = ", ".join(sorted(set(lines(git("log", "--format=%an", f"{mb}..{base}", "--", f)))))
                report.add("INFO", "overlap", f"{f} was also changed by {who} (merges cleanly, but review together)")

    # 7. optional real Odoo tests
    if args.odoo:
        run_odoo_tests(cfg, touched, report)

    # report
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    section("Results")
    for level, area, message in sorted(report.items, key=lambda i: order[i[0]]):
        say(f"  [{level:5}] {area:13} {message}")
    if not report.items:
        say("  everything looks good")
    if not args.odoo:
        say("  [INFO ] odoo tests    not run locally - Odoo.sh runs them after push"
            + ("" if (cfg.get("odoo") or {}).get("bin") else " (configure 'odoo' in .git/teamflow.json to run locally)"))
    errors, warns = report.count("ERROR"), report.count("WARN")
    say()
    say(f"check: {'FAILED' if errors else 'PASSED'} - {errors} error(s), {warns} warning(s)")
    return 1 if errors else 0


def check_csv(f, path, report):
    try:
        rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        report.add("ERROR", "csv", f"{f}: {exc}")
        return
    if not rows:
        return
    width = len(rows[0])
    for number, row in enumerate(rows[1:], start=2):
        if row and len(row) != width:
            report.add("ERROR", "csv", f"{f}:{number}: {len(row)} columns, header has {width}")
    if path.name == "ir.model.access.csv":
        ids = [r[0] for r in rows[1:] if r]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            report.add("ERROR", "security", f"{f}: duplicate ids {', '.join(dupes)}")


def check_manifest(mod, root, files, base, cfg, report):
    manifest_path = root / mod / "__manifest__.py"
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    try:
        node = next(n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Dict))
        manifest = ast.literal_eval(node)
    except (ValueError, SyntaxError, StopIteration) as exc:
        report.add("ERROR", "manifest", f"{mod}/__manifest__.py cannot be read: {exc}")
        return
    listed = set()
    for key in ("data", "demo"):
        for entry in manifest.get(key, []) or []:
            listed.add(entry)
            if not (root / mod / entry).is_file():
                report.add("ERROR", "manifest", f"{mod}: '{entry}' is listed in '{key}' but the file does not exist")
    for f in files:
        rel = f[len(mod) + 1:] if f.startswith(mod + "/") else None
        if not rel or not (root / f).is_file():
            continue
        top = rel.split("/", 1)[0]
        if top in ("views", "data", "security", "wizard", "wizards", "report", "reports") and rel.endswith((".xml", ".csv")):
            if rel not in listed:
                report.add("WARN", "manifest", f"{mod}: '{rel}' is not in the manifest data list (Odoo won't load it)")

    if cfg.get("version_bump") != "odoo-manifest":
        return
    team = version_at(base, mod) if ref_exists(base) else None
    mine = manifest_version_text(text)
    meaningful = [f for f in files if f.startswith(mod + "/") and "/tests/" not in f
                  and not f.endswith((".md", ".txt")) and "/static/" not in f]
    if team and mine:
        if version_tuple(mine) < version_tuple(team):
            report.add("ERROR", "version", f"{mod}: your version {mine} is LOWER than the team's {team}")
        elif mine == team and meaningful:
            report.add("WARN", "version", f"{mod}: code changed but version still {mine} "
                                          f"(team convention: bump it -> /amer-save does this)")
        if mine != team:
            migrations = root / mod / "migrations"
            if migrations.is_dir() and any(f.startswith(f"{mod}/migrations/") for f in files):
                folders = {p.name for p in migrations.iterdir() if p.is_dir()}
                new = [f.split("/")[2] for f in files if f.startswith(f"{mod}/migrations/") and len(f.split("/")) > 3]
                for folder in sorted(set(new)):
                    if folder in folders and version_tuple(folder) > version_tuple(mine):
                        report.add("ERROR", "version", f"{mod}: migration folder {folder} is newer than manifest {mine} (it will not run)")


def run_odoo_tests(cfg, modules, report):
    odoo = cfg.get("odoo") or {}
    if not odoo.get("bin") or not odoo.get("database"):
        report.add("WARN", "odoo tests", "not configured: set odoo.bin / odoo.config / odoo.database in .git/teamflow.json")
        return
    if not modules:
        report.add("INFO", "odoo tests", "no Odoo module changed")
        return
    names = [Path(m).name for m in modules]
    cmd = [sys.executable, odoo["bin"]] if odoo["bin"].endswith(".py") or odoo["bin"].endswith("odoo-bin") else [odoo["bin"]]
    if odoo.get("config"):
        cmd += ["-c", odoo["config"]]
    cmd += ["-d", odoo["database"], "-u", ",".join(names), "--test-enable",
            "--test-tags", ",".join(f"/{n}" for n in names), "--stop-after-init", "--log-level=test"]
    say("running: " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = proc.stdout + proc.stderr
    failures = [l for l in output.splitlines() if re.search(r"\b(ERROR|FAIL)\b", l)]
    if proc.returncode != 0 or failures:
        for line in failures[:15]:
            report.add("ERROR", "odoo tests", line.strip()[:160])
        if not failures:
            report.add("ERROR", "odoo tests", f"odoo exited with code {proc.returncode}")
    else:
        report.add("INFO", "odoo tests", f"passed for {', '.join(names)}")


# ----------------------------------------------------------------------------- bump

def cmd_bump(args):
    cfg = load_config()
    root = repo_root()
    mod = args.module.strip("/")
    path = root / mod / "__manifest__.py"
    if not path.is_file():
        raise FlowError(f"{mod}/__manifest__.py not found. Modules: {', '.join(modules_in_repo(root))}", 3)
    text = path.read_text(encoding="utf-8")
    mine = manifest_version_text(text)
    team = version_at(base_ref(cfg), mod) if ref_exists(base_ref(cfg)) else None
    if args.check_only:
        say(f"{mod}: team {team} / yours {mine}")
        return 0
    if team and mine and version_tuple(mine) > version_tuple(team) and not args.force:
        say(f"{mod}: already bumped ({team} -> {mine}); nothing to do")
        return 0
    start = max([v for v in (mine, team) if v], key=version_tuple)
    parts = start.split(".")
    parts[-1] = str(int(parts[-1]) + 1) if parts[-1].isdigit() else parts[-1] + ".1"
    new = ".".join(parts)
    path.write_text(VERSION_RE.sub(lambda m: f"{m.group(1)}{new}{m.group(3)}", text, count=1), encoding="utf-8")
    say(f"{mod}: {mine} -> {new}" + (f" (team is at {team})" if team else ""))
    return 0


# ----------------------------------------------------------------------------- pr

def cmd_pr(args):
    cfg = load_config()
    if cfg.get("_unsaved"):
        raise FlowError("Run /amer-setup once in this project before opening pull requests.", 3)
    branch = current_branch()
    if branch == cfg["base_branch"] or branch in PROTECTED:
        raise FlowError(f"Refusing to push '{branch}' - it is a shared branch. Work on your own branch.", 3)
    if in_progress_operation():
        raise FlowError("A merge/rebase is in progress. Finish it first.", 3)
    if dirty_files() and not args.allow_dirty:
        raise FlowError("There are uncommitted changes. Commit them (/amer-save) or they will not be in the PR.", 3)
    base = base_ref(cfg)
    if ref_exists(base) and ahead_behind("HEAD", base)[0] == 0:
        raise FlowError(f"Nothing to send: '{branch}' has no commits that {base} doesn't already have.", 3)

    push = ["git", "push", "-u", cfg["fork_remote"], f"HEAD:refs/heads/{branch}"]
    if args.force_with_lease:
        push.insert(2, "--force-with-lease")
    proc = run(push, check=False)
    if proc.returncode != 0:
        msg = proc.stderr.strip()
        if "rejected" in msg or "non-fast-forward" in msg or "fetch first" in msg:
            raise FlowError("GitHub has commits on this branch that you don't have. Run /amer-start (sync) and "
                            "ship again. Never force-push unless you are sure.", 3)
        raise FlowError(f"push failed:\n{msg}")
    say(f"pushed '{branch}' to {cfg['fork_remote']}")

    title = args.title or git("log", "-1", "--format=%s")
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else ""
    repo = cfg["upstream_repo"]
    same_repo = cfg["fork_remote"] == cfg["upstream_remote"]
    head = branch if same_repo else f"{cfg['fork_owner']}:{branch}"

    if gh_ready() and repo:
        proc = run(["gh", "pr", "list", "--repo", repo, "--head", branch, "--state", "open",
                    "--json", "number,url,headRepositoryOwner"], check=False)
        prs = json.loads(proc.stdout or "[]") if proc.returncode == 0 else []
        prs = [p for p in prs if same_repo or p.get("headRepositoryOwner", {}).get("login") == cfg["fork_owner"]]
        if prs:
            say(f"an open pull request already exists - your new commits were added to it:\n  {prs[0]['url']}")
            return 0
        cmd = ["gh", "pr", "create", "--repo", repo, "--base", cfg["base_branch"], "--head", head, "--title", title]
        cmd += ["--body-file", args.body_file] if args.body_file else ["--body", ""]
        if args.draft:
            cmd.append("--draft")
        proc = run(cmd, check=False)
        if proc.returncode == 0:
            say(f"pull request created:\n  {proc.stdout.strip().splitlines()[-1]}")
            return 0
        say(f"! gh could not create the PR ({proc.stderr.strip()[:200]}); falling back to the browser")

    if not repo:
        raise FlowError("Pushed, but the upstream is not a GitHub repo - open the pull request manually.", 3)
    query = {"expand": "1", "title": title}
    if body:
        query["body"] = body[:5500] + ("\n\n_(description truncated)_" if len(body) > 5500 else "")
    url = f"https://github.com/{repo}/compare/{cfg['base_branch']}...{head}?" + urllib.parse.urlencode(query)
    say("open this page and press 'Create pull request' (title and description are already filled in).")
    say("If GitHub shows an existing open pull request instead, your commits were already added to it.")
    say(f"  {url}")
    if not args.no_open:
        webbrowser.open(url)
    return 0


def cmd_undo_commit(args):
    cfg = load_config()
    if in_progress_operation():
        raise FlowError("A merge/rebase is in progress - use 'git merge --abort' instead.", 3)
    head = git("rev-parse", "HEAD")
    containing = lines(git("branch", "-r", "--contains", head))
    if containing:
        raise FlowError("The last commit is already on GitHub (" + ", ".join(c.strip() for c in containing[:3]) +
                        "). Undoing it would rewrite shared history. Make a new fix commit instead, "
                        "or 'git revert HEAD' to cancel it with a new commit.", 3)
    if len(git("rev-list", "--parents", "-n", "1", "HEAD").split()) > 2:
        raise FlowError("The last commit is a merge. Ask the AI to help undo it safely.", 3)
    subject = git("log", "-1", "--format=%h %s")
    git("reset", "--soft", "HEAD~1")
    say(f"undid commit {subject}. Your changes are kept and still staged.")
    return 0


# ----------------------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(prog="flow", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("setup")
    p.add_argument("--write", action="store_true")
    p.add_argument("--no-fetch", action="store_true")
    p.add_argument("--base-branch", dest="base_branch")
    p.add_argument("--upstream-remote", dest="upstream_remote")
    p.add_argument("--fork-remote", dest="fork_remote")
    p.add_argument("--mode", choices=["single", "feature"])
    p.add_argument("--work-branch", dest="work_branch")
    p.add_argument("--feature-prefix", dest="feature_prefix")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("status")
    p.add_argument("--no-fetch", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("sync")
    p.add_argument("--new", metavar="NAME", help="create a fresh feature branch from the team's latest base")
    p.add_argument("--stash", action="store_true", help="set uncommitted changes aside during the sync")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("changes")
    p.set_defaults(func=cmd_changes)

    p = sub.add_parser("check")
    p.add_argument("--all", action="store_true", help="check every tracked file, not only changed ones")
    p.add_argument("--odoo", action="store_true", help="also run the module's Odoo tests locally")
    p.add_argument("--no-fetch", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("bump")
    p.add_argument("module")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--force", action="store_true", help="bump again even if already above the team version")
    p.set_defaults(func=cmd_bump)

    p = sub.add_parser("pr")
    p.add_argument("--title")
    p.add_argument("--body-file")
    p.add_argument("--draft", action="store_true")
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--allow-dirty", action="store_true")
    p.add_argument("--force-with-lease", action="store_true")
    p.set_defaults(func=cmd_pr)

    p = sub.add_parser("undo-commit")
    p.set_defaults(func=cmd_undo_commit)

    args = parser.parse_args(argv)
    try:
        if args.cmd != "doctor":
            repo_root()
        return args.func(args)
    except FlowError as exc:
        say(f"\nSTOP: {exc}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
