"""
Cross-file fact-consistency checks.

This catches a class of bug that link-checking and parser-validation miss:
two files that each parse cleanly and link to each other, but disagree on a
concrete claim (a version floor, a config key location, a numeric policy
bound). Over five rounds of LLM review on this skill, every drift bug
eventually surfaced — but each one cost a review cycle. The rules below
encode the lessons so the next drift gets caught locally in milliseconds.

Each rule is a small named function returning a list of problem strings.
Adding a rule means appending another function to RULES. The rules read
files directly rather than parsing — string-grep is sufficient and robust
to surrounding markdown changes.

Exit 0 if every rule passes; 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (SKILL_ROOT / rel).read_text(encoding="utf-8")


# ── rule helpers ────────────────────────────────────────────────────────────
def _require_all(text: str, needles: list[str], where: str) -> list[str]:
    return [
        f"{where}: expected to contain `{n}` but did not"
        for n in needles
        if n not in text
    ]


def _forbid_any(text: str, needles: list[str], where: str) -> list[str]:
    return [
        f"{where}: forbidden phrase `{n}` is present (regression marker)"
        for n in needles
        if n in text
    ]


# ── rules ───────────────────────────────────────────────────────────────────
def rule_pnpm_version_boundaries() -> list[str]:
    """
    references/package-managers/pnpm.md must walk through all three pnpm
    version boundaries that affect the example: 10.16 (minimumReleaseAge
    introduced), 10.17 (glob in minimumReleaseAgeExclude), 10.26
    (blockExoticSubdeps default-on + allowBuilds). If the file mentions
    only one, a user on the wrong version gets a partially-applied config.
    """
    text = _read("references/package-managers/pnpm.md")
    return _require_all(
        text,
        ["10.16", "10.17", "10.26"],
        where="references/package-managers/pnpm.md",
    )


def rule_skill_md_pnpm_floor() -> list[str]:
    """
    SKILL.md's Quick Wins table row for pnpm must mention 10.26 as the
    effective floor — the example file uses blockExoticSubdeps and
    allowBuilds, both 10.26+. Citing only 10.16 would mislead a user on
    10.16 to think the whole example file works for them.
    """
    text = _read("SKILL.md")
    # The pnpm row of the table. Find any line starting with `| pnpm`.
    rows = [
        line
        for line in text.splitlines()
        if line.startswith("| pnpm ")
    ]
    problems = []
    if not rows:
        return ["SKILL.md: Quick Wins table missing a pnpm row"]
    row = rows[0]
    if "10.26" not in row:
        problems.append(
            f"SKILL.md pnpm table row missing `10.26` — got: {row!r}"
        )
    return problems


def rule_npm_package_manager_pin() -> list[str]:
    """
    references/package-managers/npm.md tells users to pin `packageManager`
    via corepack. If it pins a version below 11.10, the pin defeats the
    very `min-release-age` setting the file is teaching. Reviewer rounds
    found `npm@10.5.0` here — a pre-`min-release-age` version.
    """
    text = _read("references/package-managers/npm.md")
    pins = re.findall(r'packageManager"\s*:\s*"npm@(\d+)\.(\d+)\.\d+', text)
    if not pins:
        return [
            "references/package-managers/npm.md: expected a "
            '`"packageManager": "npm@X.Y.Z..."` example, found none'
        ]
    problems = []
    for major, minor in pins:
        version = f"{major}.{minor}"
        if int(major) < 11 or (int(major) == 11 and int(minor) < 10):
            problems.append(
                f"references/package-managers/npm.md: packageManager pin "
                f"`npm@{version}.*` is below 11.10 — `min-release-age` "
                f"requires npm 11.10+ (silent ignore otherwise)"
            )
    return problems


def rule_dependabot_patch_floor() -> list[str]:
    """
    SKILL.md states the global cooldown floor as 3 days. The Dependabot
    example's comment must not advertise a patch lower bound below 3 days
    — reviewer round 4 caught `patch 1` here, which would invite users to
    set `semver-patch-days: 1` while believing they're within policy.
    """
    text = _read("examples/dependabot/dependabot.yml")
    problems = []
    # Look for "patch <n>" in the comment block where the bound is stated.
    # The hazardous form is anything below 3.
    for m in re.finditer(r"patch\s+(\d+)", text):
        n = int(m.group(1))
        if n < 3:
            problems.append(
                f"examples/dependabot/dependabot.yml: comment claims a "
                f"`patch {n}` lower bound, below SKILL.md's stated 3-day "
                f"global floor"
            )
    return problems


def rule_pnpm_killswitch_location() -> list[str]:
    """
    Anywhere this skill shows a pnpm lifecycle-script kill-switch, it MUST
    use `pnpm-workspace.yaml` with `ignoreScripts: true` — NOT `.npmrc`
    with `ignore-scripts=true`. pnpm reads only auth/registry from
    `.npmrc`; behavior settings there are a silent no-op for pnpm.

    Detect by looking at the pnpm subsection of
    `lifecycle-script-allowlists.md` and confirming the kill-switch shown
    there is the yaml form.
    """
    text = _read("references/lifecycle-script-allowlists.md")
    # Find the `### pnpm` section through the next `### ` heading.
    m = re.search(r"^###\s+pnpm[^\n]*\n(.*?)(?=^###\s|\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return [
            "references/lifecycle-script-allowlists.md: no `### pnpm` "
            "section found — structure changed?"
        ]
    section = m.group(1)
    problems = []
    if "ignoreScripts: true" not in section:
        problems.append(
            "references/lifecycle-script-allowlists.md `### pnpm` section: "
            "expected `ignoreScripts: true` (the workspace-yaml form)"
        )
    # Soft-detect the wrong form: a fenced `.npmrc` block in the pnpm
    # section showing `ignore-scripts=true`.
    if re.search(r"```ini[\s\S]*?ignore-scripts\s*=\s*true[\s\S]*?```", section):
        problems.append(
            "references/lifecycle-script-allowlists.md `### pnpm` section: "
            "contains `ignore-scripts=true` in `.npmrc` form — that is a "
            "silent no-op for pnpm. Use `pnpm-workspace.yaml` with "
            "`ignoreScripts: true` instead"
        )
    return problems


def rule_lockfile_regex_coverage() -> list[str]:
    """
    SKILL.md and verification.md both show a `git ls-files | grep -E ...`
    command. The regex must explicitly include `package-lock.json` and
    `pnpm-lock.yaml` — the older `lock(file)?$|\\.lock\\.` form silently
    failed on those two names (hyphen-lock-dot, not dot-lock-dot).
    """
    problems = []
    for rel in ("SKILL.md", "references/verification.md"):
        text = _read(rel)
        # Look specifically at `git ls-files | grep -E '...'` invocations —
        # those are the lockfile-detection commands. Other `grep -E`
        # commands in these files (e.g. the pnpm-workspace.yaml settings
        # check) are out of scope for this rule.
        for m in re.finditer(r"git\s+ls-files\s*\|\s*grep\s+-E\s+'([^']+)'", text):
            pat = m.group(1)
            if "package-lock" not in pat or "pnpm-lock" not in pat:
                problems.append(
                    f"{rel}: lockfile regex `{pat}` does not enumerate "
                    f"`package-lock.json` and `pnpm-lock.yaml` literally"
                )
    return problems


def rule_yarn_enable_scripts_workspace_claim() -> list[str]:
    """
    Yarn upstream docs are explicit: `enableScripts: false` only disables
    postinstall scripts for THIRD-PARTY packages — workspace packages
    always run their own postinstall regardless. A round-2 reviewer
    misclaim led these files to assert "applies to workspace too"; the
    correction landed in round 4. This rule flags any re-introduction of
    the false wording.
    """
    targets = [
        "references/package-managers/yarn.md",
        "references/lifecycle-script-allowlists.md",
        "examples/yarn/.yarnrc.yml",
    ]
    forbidden = [
        "BOTH third-party AND workspace",
        "workspace packages too",
        "workspace packages included",
    ]
    problems = []
    for rel in targets:
        text = _read(rel)
        for f in forbidden:
            if f in text:
                problems.append(
                    f"{rel}: contains forbidden phrase `{f}` — "
                    f"contradicts Yarn upstream docs (workspaces always "
                    f"run their own postinstall regardless of "
                    f"`enableScripts`)"
                )
    return problems


def rule_uv_audit_command_location() -> list[str]:
    """
    `uv audit` lives at the top level of the `uv` CLI, NOT under `uv pip`.
    `uv pip audit` does not exist and yields `error: unrecognized
    subcommand 'audit'`. End-to-end testing against uv 0.11.14 in a fresh
    Python project caught this — users following the SKILL would type the
    command, see the error, and have no working audit step.
    """
    text = _read("references/package-managers/uv.md")
    if "uv pip audit" in text:
        return [
            "references/package-managers/uv.md: contains `uv pip audit` "
            "— that command does not exist. The audit subcommand is at "
            "the top level: `uv audit`."
        ]
    return []


def rule_bun_no_phantom_config_command() -> list[str]:
    """
    references/package-managers/bun.md must NOT recommend
    `bun pm config get install.<key>` — that subcommand does not exist
    (verified against Bun 1.3.11; `bun pm` has no `config` subcommand at
    all). End-to-end testing against a real SvelteKit + Bun project caught
    this: users following the SKILL would type the command, see "unknown
    command", and have no way to verify their hardening took effect.
    """
    text = _read("references/package-managers/bun.md")
    if "bun pm config get" in text:
        return [
            "references/package-managers/bun.md: contains "
            "`bun pm config get` — that subcommand does not exist in "
            "`bun pm`. Verify settings via functional install test or "
            "by inspecting `node_modules/.bun/` for linker shape."
        ]
    return []


def rule_actions_sha_pin_v6() -> list[str]:
    """
    examples/github-actions/release-with-oidc.yml comments its SHA pins
    as `actions/checkout@v6.0.0` / `actions/setup-node@v6.0.0`. The
    referenced SHAs must be the actual v6.0.0 commits. Reviewer round 4
    caught these pointing at v5.x SHAs. This check is offline — it pins
    the known-good v6.0.0 SHAs and verifies the workflow uses them.
    """
    text = _read("examples/github-actions/release-with-oidc.yml")
    expected = {
        "actions/checkout": "1af3b93b6815bc44a9784bd300feb67ff0d1eeb3",
        "actions/setup-node": "2028fbc5c25fe9cf00d9f06a71cc4710d4507903",
    }
    problems = []
    for action, sha in expected.items():
        # Walk all `uses: <action>@<ref>` for this action.
        found_refs = re.findall(rf"uses:\s*{re.escape(action)}@([a-f0-9]+)\b", text)
        if not found_refs:
            problems.append(
                f"examples/github-actions/release-with-oidc.yml: expected "
                f"a `uses: {action}@<sha>` line, none found"
            )
            continue
        for ref in found_refs:
            if ref != sha:
                problems.append(
                    f"examples/github-actions/release-with-oidc.yml: "
                    f"`{action}@{ref}` does not match the documented "
                    f"v6.0.0 SHA `{sha}`"
                )
    return problems


# ── runner ──────────────────────────────────────────────────────────────────
RULES = [
    rule_pnpm_version_boundaries,
    rule_skill_md_pnpm_floor,
    rule_npm_package_manager_pin,
    rule_dependabot_patch_floor,
    rule_pnpm_killswitch_location,
    rule_lockfile_regex_coverage,
    rule_yarn_enable_scripts_workspace_claim,
    rule_bun_no_phantom_config_command,
    rule_uv_audit_command_location,
    rule_actions_sha_pin_v6,
]


def main() -> int:
    print(f"[check_consistency] root: {SKILL_ROOT}")
    total_problems = 0
    for rule in RULES:
        problems = rule()
        if problems:
            print(f"  FAIL  {rule.__name__}")
            for p in problems:
                print(f"        → {p}")
            total_problems += len(problems)
        else:
            print(f"  ok    {rule.__name__}")
    print()
    if total_problems:
        print(f"[check_consistency] {total_problems} problem(s)")
        return 1
    print(f"[check_consistency] all {len(RULES)} rules pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
