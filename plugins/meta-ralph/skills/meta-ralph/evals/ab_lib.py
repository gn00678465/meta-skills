"""Sandbox + filesystem utilities used only by ab_harness.py.

Intentionally separate from run_evals.py so the existing driver eval suite
stays untouched. Duplication is small (~30 lines of sandbox plumbing) and
intentional.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRESETS_DIR = HERE / "ab_presets"
TEMPLATES_DIR = HERE.parent / "templates"


def make_sandbox(prefix: str) -> Path:
    """Temp dir + git init -b main + empty initial commit + core.autocrlf=false."""
    box = Path(tempfile.mkdtemp(prefix=prefix))
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    _run(["git", "init", "-q", "-b", "main"], cwd=box, env=env)
    _run(["git", "config", "user.email", "abharness@local"], cwd=box)
    _run(["git", "config", "user.name", "ab-harness"], cwd=box)
    _run(["git", "config", "core.autocrlf", "false"], cwd=box)
    _run(["git", "commit", "--allow-empty", "-q", "-m", "init"], cwd=box, env=env)
    return box


def seed_preset(sandbox: Path, preset_name: str) -> None:
    """Drop a preset prd.json + stub .ralph/ into the sandbox so amend fixtures
    see a real-looking existing scaffold."""
    preset_path = PRESETS_DIR / f"{preset_name}.json"
    if not preset_path.exists():
        raise FileNotFoundError(f"preset not found: {preset_path}")
    (sandbox / "prd.json").write_bytes(preset_path.read_bytes())
    ralph_dir = sandbox / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    src_driver = TEMPLATES_DIR / "ralph" / "ralph.sh.tpl"
    dst_driver = ralph_dir / "ralph.sh"
    dst_driver.write_bytes(src_driver.read_bytes().replace(b"\r\n", b"\n"))
    os.chmod(dst_driver, 0o755)
    (ralph_dir / "progress.txt").write_bytes(b"## Codebase Patterns\n")
    runbook_src = TEMPLATES_DIR / "RUNBOOK.md.tpl"
    if runbook_src.exists():
        (ralph_dir / "RUNBOOK.md").write_bytes(
            runbook_src.read_bytes().replace(b"\r\n", b"\n")
        )
    (ralph_dir / "prompt.md").write_bytes(
        b"# Ralph Agent Instructions\n\nFollow CLAUDE.md.\n"
    )
    (sandbox / ".gitignore").write_bytes(
        b".ralph/progress.txt\n.ralph/.lock\n.ralph/.complete\n"
        b".ralph/.commit-failure\n.ralph/.stop\n"
    )
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    _run(["git", "add", "-A"], cwd=sandbox, env=env)
    _run(["git", "commit", "-q", "-m", "seed: ab-harness preset"], cwd=sandbox, env=env)


def snapshot_files(root: Path) -> dict[str, bytes]:
    """Recursively capture all files under `root` (excluding .git internals).
    Keys are POSIX-style relative paths so cross-platform comparisons work.
    Values are raw bytes."""
    out: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/") or rel == ".git":
            continue
        out[rel] = path.read_bytes()
    return out


def hash_tree(root: Path) -> str:
    """SHA-256 over a sorted list of (relpath, content-sha256) pairs.
    Used by the harness to check B's templates/scripts/reference match A's."""
    items: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        items.append((rel, digest))
    h = hashlib.sha256()
    for rel, digest in items:
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(digest.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def cleanup(sandbox: Path, keep: bool) -> None:
    if keep or not sandbox.exists():
        return
    shutil.rmtree(sandbox, ignore_errors=True)


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    """Run a subprocess and raise on non-zero. stdout/stderr swallowed."""
    res = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                         encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(cmd)} (rc={res.returncode})\n"
            f"stderr: {res.stderr}"
        )
