#!/usr/bin/env python3
"""Validate an eval-skills temp workspace before aggregation/reporting.

Usage:
    python validate_workspace.py <workspace>/temp

The checker is intentionally small and dependency-free. It verifies the layout
and metadata that most often cause misleading reports when missing.
"""

import argparse
import json
import sys
from pathlib import Path


REQUIRED_TOP_LEVEL = ["target_skill_source.json", "skill_profile.json"]

REQUIRED_RUN_FILES = [
    "transcript.md",
    "timing.json",
    "metrics.json",
    "grading.json",
]


def version_sort_key(p: Path) -> tuple[int, str]:
    suffix = p.name.removeprefix("version_")
    if len(suffix) == 1 and suffix.isalpha():
        return (ord(suffix.lower()) - ord("a"), p.name)
    return (10**6, p.name)


def load_json(path: Path, errors: list[str]):
    if not path.exists():
        errors.append(f"Missing required file: {path}")
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path}: {exc}")
        return None


def check_run_dir(run_dir: Path, errors: list[str]):
    if not run_dir.is_dir():
        errors.append(f"Missing run directory: {run_dir}")
        return
    outputs = run_dir / "outputs"
    if not outputs.is_dir():
        errors.append(f"Missing outputs directory: {outputs}")
    elif not any(outputs.iterdir()):
        errors.append(f"Outputs directory is empty: {outputs}")
    raw_outputs = run_dir / "raw_outputs"
    if not raw_outputs.is_dir():
        errors.append(f"Missing raw_outputs directory: {raw_outputs}")
    for name in REQUIRED_RUN_FILES:
        p = run_dir / name
        if not p.exists():
            errors.append(f"Missing run file: {p}")
        elif p.suffix == ".json":
            data = load_json(p, errors)
            if name == "grading.json" and isinstance(data, dict):
                summary = data.get("summary")
                if not isinstance(summary, dict) or not isinstance(summary.get("pass_rate"), (int, float)):
                    errors.append(f"grading.json missing numeric summary.pass_rate: {p}")


def version_names_for_scenario(scenario_dir: Path, mapping) -> list[str]:
    names: list[str] = []
    if isinstance(mapping, dict):
        names.extend(name for name in mapping if name.startswith("version_"))
    names.extend(
        d.name for d in sorted(scenario_dir.glob("version_*"), key=version_sort_key)
        if d.is_dir()
    )
    return list(dict.fromkeys(names))


def validate(workspace: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not workspace.is_dir():
        return [f"Workspace does not exist or is not a directory: {workspace}"], warnings

    for name in REQUIRED_TOP_LEVEL:
        load_json(workspace / name, errors)

    scenario_set = load_json(workspace / "scenario_set.json", errors) or {}
    context = load_json(workspace / "evaluation_context.json", errors) or {}
    label_key = load_json(workspace / "label_key.json", errors) or {}

    if context.get("sampling_mode") != "standard":
        errors.append("evaluation_context.json must set sampling_mode to 'standard'")
    if context.get("runs_per_configuration") != 3:
        errors.append("evaluation_context.json must set runs_per_configuration to 3")
    allowed_levels = {"low", "medium", "high"}
    for field in ("baseline_contamination_risk", "artifact_leakage_risk", "visual_comparability"):
        if context.get(field) not in allowed_levels:
            errors.append(f"evaluation_context.json {field} must be low, medium, or high")
    if context.get("blind_level") not in {"strong_blind", "weak_blind", "not_blind"}:
        errors.append("evaluation_context.json blind_level is invalid")

    scenarios = scenario_set.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("scenario_set.json must contain a non-empty scenarios array")
        scenarios = []

    seen_ids = set()
    for scenario in scenarios:
        sid = scenario.get("id")
        if sid is None:
            errors.append("Every scenario must have an id")
            continue
        if sid in seen_ids:
            errors.append(f"Duplicate scenario id: {sid}")
            continue
        seen_ids.add(sid)
        expectations = scenario.get("expectations")
        if not isinstance(expectations, list) or not expectations:
            errors.append(f"scenario-{sid} must define a non-empty expectations array")
        scenario_name = f"scenario-{sid}"
        scenario_dir = workspace / scenario_name
        if not scenario_dir.is_dir():
            errors.append(f"Missing scenario directory: {scenario_dir}")
            continue

        load_json(scenario_dir / "eval_metadata.json", errors)
        comparison = load_json(scenario_dir / "comparison.json", errors)
        load_json(scenario_dir / "analysis.json", errors)

        mapping = label_key.get(scenario_name)
        if not isinstance(mapping, dict):
            errors.append(f"label_key.json missing mapping for {scenario_name}")
            mapping = {}
        else:
            version_keys = [k for k in mapping if k.startswith("version_")]
            configs = [mapping.get(k) for k in version_keys]
            if len(version_keys) < 2:
                errors.append(f"label_key.json {scenario_name} must map at least two version_* entries")
            if any(not isinstance(config, str) or not config for config in configs):
                errors.append(f"label_key.json {scenario_name} version mappings must be non-empty strings")
            if len(set(configs)) != len(configs):
                errors.append(f"label_key.json {scenario_name} must not assign the same configuration twice")

        version_names = version_names_for_scenario(scenario_dir, mapping)
        if len(version_names) < 2:
            errors.append(f"{scenario_dir} must contain at least two version_* directories")
        mapped_names = {name for name in mapping if name.startswith("version_")} if isinstance(mapping, dict) else set()
        directory_names = {d.name for d in scenario_dir.glob("version_*") if d.is_dir()}
        if mapped_names != directory_names:
            errors.append(
                f"{scenario_name} version directories must exactly match label_key mappings "
                f"(mapped={sorted(mapped_names)}, directories={sorted(directory_names)})"
            )
        if isinstance(comparison, dict):
            valid_winners = {"TIE"} | {
                name.removeprefix("version_").upper() for name in mapped_names
            }
            if str(comparison.get("winner", "")).upper() not in valid_winners:
                errors.append(
                    f"{scenario_name} comparison winner must be one of {sorted(valid_winners)}"
                )
            compared = comparison.get("versions_compared")
            expected_labels = sorted(
                name.removeprefix("version_").upper() for name in mapped_names
            )
            if not isinstance(compared, list) or sorted(compared) != expected_labels:
                errors.append(
                    f"{scenario_name} comparison versions_compared must equal {expected_labels}"
                )

        for version in version_names:
            version_dir = scenario_dir / version
            if not version_dir.is_dir():
                errors.append(f"Missing version directory: {version_dir}")
                continue
            run_dirs = sorted(d for d in version_dir.glob("run-*") if d.is_dir())
            if len(run_dirs) != 3:
                errors.append(f"{version_dir} must contain exactly 3 run-* directories for standard mode")
            for idx in range(1, 4):
                check_run_dir(version_dir / f"run-{idx}", errors)

    scenario_dirs = sorted(d.name for d in workspace.glob("scenario-*") if d.is_dir())
    declared = {f"scenario-{s.get('id')}" for s in scenarios if s.get("id") is not None}
    extra = [name for name in scenario_dirs if name not in declared]
    if extra:
        warnings.append(f"Scenario directories not declared in scenario_set.json: {', '.join(extra)}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()

    errors, warnings = validate(args.workspace.resolve())

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Validation failed with {len(errors)} error(s)", file=sys.stderr)
        return 1

    print("Workspace validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
