"""
Walk every `*.md` file shipped with this skill and verify every internal
relative link `[text](path)` resolves to a real file or directory.

What this catches:
- `renovate.json` linked from a doc when the file is actually `renovate.json5`
- `../../examples/...` from a 1-level-deep reference when only `../examples/...`
  would resolve
- A reference file renamed without updating the link
- Anchor mistakes like `#section-name` where no matching heading exists

External URLs (`http://`, `https://`, `mailto:`) are not checked — they're not
in scope for a local static check.

Exit 0 if every relative link resolves; 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse


SKILL_ROOT = Path(__file__).resolve().parents[2]

# Match markdown links: [text](path) — including image variant ![alt](path).
# We capture the target inside the parens. The target may have an optional
# title in quotes; we strip from the first whitespace.
_MD_LINK = re.compile(r"!?\[(?P<text>[^\]]*)\]\((?P<target>[^)]+)\)")


def _is_external(target: str) -> bool:
    parsed = urlparse(target)
    return bool(parsed.scheme) and parsed.scheme not in ("",)


def _is_anchor_only(target: str) -> bool:
    return target.startswith("#")


def _split_target(target: str) -> tuple[str, str | None, str | None]:
    """
    Markdown allows `(path "title")` and fragments `(path#anchor)`.
    Return (path, anchor, title).
    """
    # title is anything after first unquoted whitespace
    title = None
    if " " in target:
        # title in quotes typically; split on first space
        path_part, _, rest = target.partition(" ")
        title = rest.strip()
        target = path_part
    anchor = None
    if "#" in target:
        target, _, anchor = target.partition("#")
    return target, anchor, title


def _heading_anchor_id(heading_text: str) -> str:
    """
    GitHub-style anchor slug: lowercase, spaces → hyphens, strip most
    punctuation. Good enough for this check — false negatives here would
    just be missed warnings, not silent bugs.
    """
    s = heading_text.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s.strip("-")


def _collect_anchors(md_file: Path) -> set[str]:
    anchors: set[str] = set()
    for line in md_file.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            anchors.add(_heading_anchor_id(m.group(2)))
    return anchors


def _scan_links(md_file: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, raw_target) for every link in the file."""
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(md_file.read_text(encoding="utf-8").splitlines(), 1):
        for m in _MD_LINK.finditer(line):
            found.append((lineno, m.group("target")))
    return found


def main() -> int:
    print(f"[check_links] root: {SKILL_ROOT}")

    md_files = sorted(SKILL_ROOT.rglob("*.md"))
    # Exclude evals/ (this dir) — its README is not part of the user-facing
    # documentation chain. We still want to lint it though — leave it in.

    total_links = 0
    failed = 0

    for md in md_files:
        rel_md = md.relative_to(SKILL_ROOT)
        for lineno, target in _scan_links(md):
            total_links += 1
            if _is_external(target):
                continue
            path_part, anchor, _title = _split_target(target)
            if _is_anchor_only(target):
                # In-page anchor; resolve against this same file.
                if anchor and anchor not in _collect_anchors(md):
                    print(
                        f"  FAIL  {rel_md}:{lineno}  → in-page anchor "
                        f"`#{anchor}` not found"
                    )
                    failed += 1
                continue
            if not path_part:
                # Bare anchor; handled above.
                continue
            resolved = (md.parent / path_part).resolve()
            if not resolved.exists():
                print(
                    f"  FAIL  {rel_md}:{lineno}  → `{target}` resolves to "
                    f"{resolved} (missing)"
                )
                failed += 1
                continue
            if anchor and resolved.is_file() and resolved.suffix == ".md":
                if anchor not in _collect_anchors(resolved):
                    print(
                        f"  WARN  {rel_md}:{lineno}  → anchor `#{anchor}` "
                        f"not found in {resolved.relative_to(SKILL_ROOT)}"
                    )
                    # Don't fail on anchor — slug heuristic isn't perfect.

    print()
    print(
        f"[check_links] scanned {total_links} link(s) across "
        f"{len(md_files)} markdown file(s); {failed} broken"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
