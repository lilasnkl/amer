#!/usr/bin/env python3
"""Install Amer /amer-* commands into Claude Code, omp and Antigravity.

    python install.py                 install everywhere it can
    python install.py --only omp      only one target (claude, omp, antigravity)
    python install.py --uninstall     remove from all targets

Run it again after editing the plugin to update every tool.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE / "plugin"
SKILLS = PLUGIN / "skills"
HOME = Path.home()
ENGINE_DIR = HOME / ".teamflow"
OMP_COMMANDS = HOME / ".omp" / "agent" / "commands"
PLUGIN_NAME = "amer"
MARKETPLACE = "amer-tools"
AGY_PLUGIN = HOME / ".gemini" / "config" / "plugins" / PLUGIN_NAME
CLAUDE_SKILLS = HOME / ".claude" / "skills"
# earlier releases were called "teamflow" with /flow-* commands
LEGACY_PLUGIN, LEGACY_MARKETPLACE = "teamflow", "teamflow-tools"
LEGACY_COMMANDS = ["flow-go", "flow-start", "flow-save", "flow-check", "flow-ship", "flow-status", "flow-undo", "flow-setup", "flow-help"]


def skill_names():
    return sorted(p.parent.name for p in SKILLS.glob("*/SKILL.md"))


def split_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    return (match.group(1), match.group(2)) if match else ("", text)


def find_claude():
    for candidate in (shutil.which("claude"), HOME / ".local" / "bin" / "claude.exe", HOME / ".local" / "bin" / "claude"):
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def claude_cli(claude, *args):
    proc = subprocess.run([claude, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def find_omp():
    return shutil.which("omp") or (HOME / ".omp").is_dir()


def find_antigravity():
    return shutil.which("antigravity") or (HOME / ".gemini" / "antigravity").is_dir() or (HOME / ".gemini" / "config").is_dir()


def detected_tools():
    found = {"claude": bool(find_claude() or (HOME / ".claude").is_dir()), "omp": bool(find_omp()),
             "antigravity": bool(find_antigravity())}
    return [name for name, ok in found.items() if ok]


def preflight():
    if sys.version_info < (3, 8):
        sys.exit("Amer needs Python 3.8 or newer.")
    if not shutil.which("git"):
        sys.exit("git was not found. Install Git first: https://git-scm.com/downloads")


def install_engine():
    ENGINE_DIR.mkdir(exist_ok=True)
    shutil.copy2(PLUGIN / "scripts" / "flow.py", ENGINE_DIR / "flow.py")
    print(f"[engine]      {ENGINE_DIR / 'flow.py'}")


def install_claude():
    claude = find_claude()
    if not claude:
        CLAUDE_SKILLS.mkdir(parents=True, exist_ok=True)
        for name in skill_names():
            shutil.copytree(SKILLS / name, CLAUDE_SKILLS / name, dirs_exist_ok=True)
        print(f"[claude code] claude CLI not found -> copied skills to {CLAUDE_SKILLS}")
        return
    code, out = claude_cli(claude, "plugin", "marketplace", "add", str(HERE))
    if code != 0 and "already" not in out.lower():
        print(f"[claude code] marketplace add failed: {out}")
        return
    claude_cli(claude, "plugin", "marketplace", "update", MARKETPLACE)
    code, out = claude_cli(claude, "plugin", "install", f"{PLUGIN_NAME}@{MARKETPLACE}")
    if code == 0 or "already" in out.lower():
        # install is a no-op when the plugin exists, so always pull the latest version too
        code, out = claude_cli(claude, "plugin", "update", f"{PLUGIN_NAME}@{MARKETPLACE}")
    version = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    print(f"[claude code] {f'plugin {PLUGIN_NAME}@{MARKETPLACE} v{version} (restart Claude to load it)' if code == 0 else 'install problem: ' + out}")


def install_omp():
    OMP_COMMANDS.mkdir(parents=True, exist_ok=True)
    for name in skill_names():
        front, body = split_frontmatter((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))
        keep = [l for l in front.splitlines() if l.startswith(("description:", "argument-hint:"))]
        (OMP_COMMANDS / f"{name}.md").write_text("---\n" + "\n".join(keep) + "\n---\n" + body, encoding="utf-8")
    print(f"[omp]         {len(skill_names())} commands -> {OMP_COMMANDS}")


def install_antigravity():
    if AGY_PLUGIN.exists():
        shutil.rmtree(AGY_PLUGIN)
    (AGY_PLUGIN / "skills").mkdir(parents=True)
    (AGY_PLUGIN / "plugin.json").write_text(json.dumps({"name": PLUGIN_NAME}, indent=2), encoding="utf-8")
    for name in skill_names():
        shutil.copytree(SKILLS / name, AGY_PLUGIN / "skills" / name)
    shutil.copytree(PLUGIN / "scripts", AGY_PLUGIN / "scripts")
    print(f"[antigravity] plugin -> {AGY_PLUGIN}")


def remove_legacy():
    claude = find_claude()
    if claude:
        code, _ = claude_cli(claude, "plugin", "uninstall", f"{LEGACY_PLUGIN}@{LEGACY_MARKETPLACE}")
        claude_cli(claude, "plugin", "marketplace", "remove", LEGACY_MARKETPLACE)
    removed = 0
    for name in LEGACY_COMMANDS:
        for path in (OMP_COMMANDS / f"{name}.md", CLAUDE_SKILLS / name):
            if path.is_file():
                path.unlink()
                removed += 1
            elif path.is_dir():
                shutil.rmtree(path)
                removed += 1
    legacy_agy = AGY_PLUGIN.parent / LEGACY_PLUGIN
    if legacy_agy.exists():
        shutil.rmtree(legacy_agy)
        removed += 1
    if removed or (claude and code == 0):
        print("[cleanup]     removed the old /flow-* commands")


def uninstall(targets):
    if "claude" in targets:
        claude = find_claude()
        if claude:
            claude_cli(claude, "plugin", "uninstall", f"{PLUGIN_NAME}@{MARKETPLACE}")
            claude_cli(claude, "plugin", "marketplace", "remove", MARKETPLACE)
        for name in skill_names():
            shutil.rmtree(CLAUDE_SKILLS / name, ignore_errors=True)
        print("[claude code] removed")
    if "omp" in targets:
        for name in skill_names():
            (OMP_COMMANDS / f"{name}.md").unlink(missing_ok=True)
        print("[omp]         removed")
    if "antigravity" in targets:
        shutil.rmtree(AGY_PLUGIN, ignore_errors=True)
        print("[antigravity] removed")
    if set(targets) == {"claude", "omp", "antigravity"}:
        shutil.rmtree(ENGINE_DIR, ignore_errors=True)
        print("[engine]      removed")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma list: claude,omp,antigravity")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    preflight()
    if args.uninstall:
        uninstall(args.only.split(",") if args.only else ["claude", "omp", "antigravity"])
        return 0
    targets = args.only.split(",") if args.only else detected_tools()
    version = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    print(f"Installing Amer v{version} for: {', '.join(targets) or 'no AI tool found'}\n")
    remove_legacy()
    install_engine()
    for target in targets:
        {"claude": install_claude, "omp": install_omp, "antigravity": install_antigravity}[target]()
    skipped = [t for t in ("claude", "omp", "antigravity") if t not in targets]
    if skipped and not args.only:
        print(f"[skipped]     not found on this computer: {', '.join(skipped)} (force with --only {','.join(skipped)})")
    if not shutil.which("gh"):
        print("[tip]         install GitHub CLI for automatic pull requests: https://cli.github.com  then: gh auth login")
    print("\nDone. Restart your AI app(s), open your project and type /amer-setup (once), then /amer <task>.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
