#!/usr/bin/env python3
"""
Analyze a skill's SKILL.md and produce a skill_profile.json used to plan the eval.

This is a *deterministic first pass*. It extracts structural signals (headers,
numbered steps, bundled resources) so the evaluator does not have to re-read the whole
file from scratch every time, and so the "procedural vs holistic" judgment call
has some grounded signal behind it. The evaluator should still read SKILL.md itself
and use judgment -- this script's output is a scaffold, not a verdict.

Usage:
    python analyze_skill.py <skill-path> [--out skill_profile.json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import parse_skill_md


HEADER_RE = re.compile(r"^(#{2,4})\s+(.*)$", re.MULTILINE)
NUMBERED_STEP_RE = re.compile(r"^\s*(?:###?\s*)?(?:Step\s*)?(\d+)[\.\):]\s+(.*)$", re.MULTILINE | re.IGNORECASE)


IGNORED_PARTS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", "node_modules"}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".DS_Store"}


def find_bundled_resources(skill_path: Path) -> dict:
    resources = {"scripts": [], "references": [], "assets": []}
    for sub in ("scripts", "references", "assets"):
        d = skill_path / sub
        if d.is_dir():
            resources[sub] = sorted(
                str(p.relative_to(skill_path))
                for p in d.rglob("*")
                if p.is_file()
                and not any(
                    part in IGNORED_PARTS or part.startswith(".")
                    for part in p.relative_to(skill_path).parts
                )
                and p.suffix not in IGNORED_SUFFIXES
            )
    return resources


def extract_candidate_steps(content: str) -> list[str]:
    """Look for explicit numbered steps ('Step 1', '1.', '### 1)') in the body."""
    # Prefer headers that look like steps
    headers = HEADER_RE.findall(content)
    step_headers = [h for _, h in headers if re.match(r"^(step\s*\d+|phase\s*\d+|\d+[\.\):])", h.strip(), re.IGNORECASE)]
    if len(step_headers) >= 2:
        return step_headers

    # Fall back to inline numbered lists
    matches = NUMBERED_STEP_RE.findall(content)
    if len(matches) >= 2:
        return [text.strip() for _, text in matches]

    return []


def guess_domain(description: str) -> str:
    """Very rough domain tag from the description -- for human sanity-checking,
    not for any downstream logic. The evaluator should refine this."""
    return description.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_path", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    skill_path = args.skill_path.resolve()
    name, description, content = parse_skill_md(skill_path)

    candidate_steps = extract_candidate_steps(content)
    resources = find_bundled_resources(skill_path)

    body_lines = content.count("\n") + 1
    has_scripts = bool(resources.get("scripts"))

    # Heuristic classification -- the evaluator must confirm or override it.
    if len(candidate_steps) >= 2:
        suggested_type = "procedural"
    elif has_scripts:
        suggested_type = "procedural"  # bundled scripts usually imply a fixed pipeline
    else:
        suggested_type = "holistic"

    profile = {
        "skill_name": name,
        "skill_path": str(skill_path),
        "description": description,
        "domain_hint": guess_domain(description),
        "body_line_count": body_lines,
        "bundled_resources": resources,
        "has_bundled_scripts": has_scripts,
        "candidate_steps_detected": candidate_steps,
        "suggested_type": suggested_type,
        "note": (
            "suggested_type is a heuristic based on numbered headers/lists and "
            "the presence of scripts/. The evaluator MUST read SKILL.md directly and "
            "confirm or override this before generating prompts -- e.g. a skill "
            "with 5 numbered 'tips' is not the same as 5 sequential pipeline steps."
        ),
    }

    out_path = args.out or (
        skill_path.parent / f"{name or skill_path.name}-eval-workspace" / "temp" / "skill_profile.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(profile, indent=2, ensure_ascii=False))
    print(f"\nWrote profile to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
