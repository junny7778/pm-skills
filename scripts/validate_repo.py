#!/usr/bin/env python3
"""Validate repository invariants introduced by the Codex hardening pass."""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
REMOVED_SKILLS = {"space-image2proto", "space-url2proto"}
FORBIDDEN_SKILL_TEXT = ("mcp__Claude_in_Chrome__", "WebFetch")


def frontmatter_name(path: pathlib.Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return None
    name = re.search(r"^name:\s*([^\n]+)$", match.group(1), re.MULTILINE)
    return name.group(1).strip() if name else None


def validate() -> list[str]:
    errors: list[str] = []
    skill_files = sorted(ROOT.glob("*/SKILL.md"))
    names: dict[str, pathlib.Path] = {}
    for path in skill_files:
        name = frontmatter_name(path)
        if not name:
            errors.append(f"missing valid frontmatter name: {path.relative_to(ROOT)}")
            continue
        if name != path.parent.name:
            errors.append(f"skill name {name!r} does not match directory {path.parent.name!r}")
        if name in names:
            errors.append(f"duplicate skill name {name!r}: {names[name]} and {path}")
        names[name] = path
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_SKILL_TEXT:
            if forbidden in text:
                errors.append(f"host-specific tool reference {forbidden!r}: {path.relative_to(ROOT)}")

    for removed in REMOVED_SKILLS:
        if (ROOT / removed).exists():
            errors.append(f"removed duplicate skill still exists: {removed}")

    url_skill = (ROOT / "pm-url2proto" / "SKILL.md").read_text(encoding="utf-8")
    if "references/web-safety.md" not in url_skill or not (ROOT / "pm-url2proto/references/web-safety.md").is_file():
        errors.append("pm-url2proto must load references/web-safety.md")

    image_skill = (ROOT / "pm-image2proto" / "SKILL.md").read_text(encoding="utf-8")
    if ".pm-skill-memory/pm-image2proto/" not in image_skill:
        errors.append("pm-image2proto must use project-local memory")
    for stale in ("design_system.json", "learning_log.jsonl"):
        if (ROOT / "pm-image2proto" / "references" / stale).exists():
            errors.append(f"writable state seed remains in installed skill: {stale}")

    experiment_skill = (ROOT / "pm-experiment-designer" / "SKILL.md").read_text(encoding="utf-8")
    stats_script = ROOT / "pm-experiment-designer/scripts/experiment_stats.py"
    stats_tests = ROOT / "pm-experiment-designer/tests/test_experiment_stats.py"
    if "scripts/experiment_stats.py" not in experiment_skill or not stats_script.is_file() or not stats_tests.is_file():
        errors.append("experiment skill must include and document its verified statistics script")
    return errors


if __name__ == "__main__":
    failures = validate()
    if failures:
        print("Repository validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        raise SystemExit(1)
    print("Repository validation passed.")
