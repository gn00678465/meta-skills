"""
Native parser validation for every example file shipped with this skill.

Why: each example is an `examples/<tool>/<file>` snippet that users will paste
into their own repo. If we ship something that doesn't parse with the tool's
own parser, the user copies it, the tool silently ignores or rejects it, and
the supply-chain control isn't applied. SPEC.md's source-of-truth rule was
exactly this: examples are canonical; references quote them. Examples must
work.

Exits 0 if all files validate. Exits 1 on the first failure (still reports
every file's status so one run shows the full picture).
"""

from __future__ import annotations

import configparser
import io
import json
import re
import sys
import tomllib
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = SKILL_ROOT / "examples"


# ── YAML loader ─────────────────────────────────────────────────────────────
def _load_yaml(text: str):
    """Prefer ruamel.yaml, fall back to PyYAML. One must be installed."""
    try:
        from ruamel.yaml import YAML  # type: ignore

        return YAML(typ="safe").load(text)
    except ImportError:
        pass
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError as e:
        raise RuntimeError(
            "Neither ruamel.yaml nor pyyaml is installed. "
            "Run: pip install ruamel.yaml"
        ) from e


# ── INI-ish loader ──────────────────────────────────────────────────────────
def _load_ini_like(text: str, *, default_section: str = "DEFAULT"):
    """
    `.npmrc` / `pip.conf` are key=value config files. configparser is strict
    about section headers; `.npmrc` doesn't have one, so wrap it.
    """
    parser = configparser.ConfigParser(
        allow_no_value=True, interpolation=None, strict=False
    )
    # Detect whether file already has a [section]; if not, wrap.
    has_section = any(
        line.strip().startswith("[") and line.strip().endswith("]")
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith(";")
    )
    if not has_section:
        text = f"[{default_section}]\n{text}"
    parser.read_file(io.StringIO(text))
    return parser


# ── JSON5 loader (minimal, tolerant) ────────────────────────────────────────
_JSON5_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _strip_json5_comments(text: str) -> str:
    """
    Strip `//` line and `/* */` block comments — but only when outside string
    literals. A naive regex would eat `//` inside `"https://..."` URLs.
    """
    out: list[str] = []
    i, n = 0, len(text)
    in_string: str | None = None  # None or the quote char
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == in_string:
                in_string = None
            i += 1
            continue
        if c in ('"', "'"):
            in_string = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                # line comment: skip to end of line
                j = text.find("\n", i + 2)
                i = n if j == -1 else j
                continue
            if nxt == "*":
                # block comment: skip to */
                j = text.find("*/", i + 2)
                i = n if j == -1 else j + 2
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _load_json5(text: str):
    """
    Strip JSON5-only constructs (string-aware comments, trailing commas) and
    parse as JSON. Good enough for the `renovate.json5` we ship.
    """
    text = _strip_json5_comments(text)
    text = _JSON5_TRAILING_COMMA.sub(r"\1", text)
    return json.loads(text)


# ── Per-file validators ─────────────────────────────────────────────────────
def _validate_generic_yaml(path: Path) -> str | None:
    _load_yaml(path.read_text(encoding="utf-8"))
    return None


def _validate_generic_toml(path: Path) -> str | None:
    with path.open("rb") as f:
        tomllib.load(f)
    return None


def _validate_generic_ini(path: Path) -> str | None:
    _load_ini_like(path.read_text(encoding="utf-8"))
    return None


def _validate_renovate_json5(path: Path) -> str | None:
    _load_json5(path.read_text(encoding="utf-8"))
    return None


_SHA_PIN_RE = re.compile(r"^([\w-]+/[\w.-]+)@([a-f0-9]{40})$")


def _validate_github_actions(path: Path) -> str | None:
    """
    Parse as YAML, then walk every `uses:` and verify it's pinned to a
    40-character commit SHA (not a tag like @v6 or branch like @main).
    Tag-pinning defeats the entire purpose of the example.
    """
    doc = _load_yaml(path.read_text(encoding="utf-8"))
    jobs = (doc or {}).get("jobs") or {}
    problems = []
    for job_name, job in jobs.items():
        for i, step in enumerate(job.get("steps") or []):
            uses = step.get("uses")
            if uses is None:
                continue
            m = _SHA_PIN_RE.match(uses)
            if not m:
                problems.append(
                    f"job '{job_name}' step {i}: `uses: {uses}` is not "
                    f"pinned to a 40-char commit SHA (got non-SHA ref)"
                )
    if problems:
        return "; ".join(problems)
    return None


_DEPENDABOT_COOLDOWN_KEYS = {
    "default-days",
    "semver-major-days",
    "semver-minor-days",
    "semver-patch-days",
    "include",
    "exclude",
}


def _validate_dependabot(path: Path) -> str | None:
    """
    Parse YAML, then check the `cooldown:` block (per package-ecosystem)
    only uses documented schema keys. Dependabot silently ignores unknown
    keys — a typo here produces a zero-cooldown config with no warning.
    Reference: docs.github.com/.../configuration-options-for-the-dependabot.yml-file#cooldown
    """
    doc = _load_yaml(path.read_text(encoding="utf-8"))
    updates = (doc or {}).get("updates") or []
    problems = []
    for i, entry in enumerate(updates):
        cooldown = entry.get("cooldown")
        if cooldown is None:
            continue
        for key in cooldown:
            if key not in _DEPENDABOT_COOLDOWN_KEYS:
                problems.append(
                    f"updates[{i}].cooldown contains undocumented key "
                    f"`{key}` (Dependabot silently ignores unknown keys "
                    f"— this is a silent failure)"
                )
    if problems:
        return "; ".join(problems)
    return None


# Each entry: (relative-path, validator-fn). Validator returns None on pass,
# or a string describing the problem on fail.
TARGETS: list[tuple[str, callable]] = [
    ("bun/bunfig.toml", _validate_generic_toml),
    ("dependabot/dependabot.yml", _validate_dependabot),
    ("github-actions/release-with-oidc.yml", _validate_github_actions),
    ("npm/.npmrc", _validate_generic_ini),
    ("pip/pip.conf", _validate_generic_ini),
    ("pnpm/.npmrc", _validate_generic_ini),
    ("pnpm/pnpm-workspace.yaml", _validate_generic_yaml),
    ("pre-commit/.pre-commit-config.yaml", _validate_generic_yaml),
    ("renovate/renovate.json5", _validate_renovate_json5),
    ("uv/pyproject.toml", _validate_generic_toml),
    ("yarn/.yarnrc.yml", _validate_generic_yaml),
]


def main() -> int:
    print(f"[validate_examples] root: {EXAMPLES_DIR}")
    failed = 0
    for rel, fn in TARGETS:
        path = EXAMPLES_DIR / rel
        if not path.exists():
            print(f"  MISSING  {rel}")
            failed += 1
            continue
        try:
            problem = fn(path)
        except Exception as exc:  # parse error, etc.
            print(f"  FAIL     {rel}  → {type(exc).__name__}: {exc}")
            failed += 1
            continue
        if problem:
            print(f"  FAIL     {rel}  → {problem}")
            failed += 1
        else:
            print(f"  ok       {rel}")

    # Look for any example files we didn't validate (a new example added
    # without updating this script is itself a regression signal).
    declared = {EXAMPLES_DIR / rel for rel, _ in TARGETS}
    on_disk = {p for p in EXAMPLES_DIR.rglob("*") if p.is_file()}
    unknown = on_disk - declared
    for p in sorted(unknown):
        rel = p.relative_to(EXAMPLES_DIR)
        print(f"  UNKNOWN  {rel}  → add to TARGETS in validate_examples.py")
        failed += 1

    print()
    if failed:
        print(f"[validate_examples] {failed} problem(s)")
        return 1
    print(f"[validate_examples] all {len(TARGETS)} examples parse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
