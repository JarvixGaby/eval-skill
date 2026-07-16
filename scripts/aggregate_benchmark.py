#!/usr/bin/env python3
"""
Aggregate individual run results into benchmark summary statistics.

Reads grading.json files from run directories and produces:
- run_summary with mean, stddev, min, max for each metric
- delta between with_skill and without_skill configurations when present

Usage:
    python aggregate_benchmark.py <workspace>/temp

Example:
    python aggregate_benchmark.py benchmarks/2026-01-15T10-30-00/temp

    The script supports the standard eval-skills layout and a few legacy
    layouts for older reports. New eval-skills runs should use exactly three
    run-* directories per version.

    Eval-skills layout:
    <benchmark_dir>/
    ├── label_key.json
    └── scenario-N/
        ├── version_a/
        │   ├── run-1/grading.json
        │   └── run-2/grading.json
        └── version_b/
            └── run-1/grading.json

    Legacy eval-skills quick layout:
    <benchmark_dir>/
    ├── label_key.json
    └── scenario-N/
        ├── version_a/grading.json
        └── version_b/grading.json

    Workspace layout (from skill-creator iterations):
    <benchmark_dir>/
    └── eval-N/
        ├── with_skill/
        │   ├── run-1/grading.json
        │   └── run-2/grading.json
        └── without_skill/
            ├── run-1/grading.json
            └── run-2/grading.json

    Legacy layout (with runs/ subdirectory):
    <benchmark_dir>/
    └── runs/
        └── eval-N/
            ├── with_skill/
            │   └── run-1/grading.json
            └── without_skill/
                └── run-1/grading.json
"""

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def calculate_stats(values: list[float]) -> dict:
    """Calculate mean, stddev, min, max for a list of values."""
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    n = len(values)
    mean = sum(values) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4)
    }


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def run_dirs_for_version(version_dir: Path) -> list[Path]:
    """Return explicit run directories, with legacy single-version fallback."""
    explicit_runs = sorted(
        d for d in version_dir.glob("run-*")
        if d.is_dir() and (d / "grading.json").exists()
    )
    if explicit_runs:
        return explicit_runs
    if (version_dir / "grading.json").exists():
        return [version_dir]
    return []


def version_sort_key(p: Path) -> tuple[int, str]:
    suffix = p.name.removeprefix("version_")
    if len(suffix) == 1 and suffix.isalpha():
        return (ord(suffix.lower()) - ord("a"), p.name)
    return (10**6, p.name)


def version_dirs_for_scenario(scenario_dir: Path, mapping: dict) -> list[Path]:
    """Return version directories from label_key first, with filesystem fallback."""
    names: list[str] = []
    if isinstance(mapping, dict):
        names.extend(name for name in mapping if name.startswith("version_"))
    names.extend(
        d.name for d in sorted(scenario_dir.glob("version_*"), key=version_sort_key)
        if d.is_dir()
    )
    deduped = list(dict.fromkeys(names))
    return [scenario_dir / name for name in deduped if (scenario_dir / name).is_dir()]


def result_from_run(eval_id, config: str, run_number: int, run_dir: Path, grading: dict) -> dict:
    result = {
        "eval_id": eval_id,
        "configuration": config,
        "run_number": run_number,
        "pass_rate": grading.get("summary", {}).get("pass_rate", 0.0),
        "passed": grading.get("summary", {}).get("passed", 0),
        "failed": grading.get("summary", {}).get("failed", 0),
        "total": grading.get("summary", {}).get("total", 0),
    }

    timing = grading.get("timing", {}) or {}
    timing_file = run_dir / "timing.json"
    timing_data = load_json(timing_file, {}) or {}
    result["time_seconds"] = timing_data.get(
        "total_duration_seconds",
        timing_data.get("duration_seconds", timing.get("total_duration_seconds", 0.0)),
    )
    result["tokens"] = timing_data.get(
        "total_tokens", timing_data.get("token_usage", timing.get("total_tokens"))
    )

    metrics = grading.get("execution_metrics", {}) or {}
    metrics_data = load_json(run_dir / "metrics.json")
    if metrics_data is None:
        metrics_data = load_json(run_dir / "outputs" / "metrics.json", {})
    if metrics_data:
        metrics = {**metrics, **metrics_data}
    result["tool_calls"] = metrics.get("total_tool_calls", 0)
    if result["tokens"] is None:
        result["tokens"] = metrics.get("total_tokens")
    result["errors"] = metrics.get("errors_encountered", 0)
    result["output_chars"] = metrics.get("output_chars", 0)
    result["expectations"] = grading.get("expectations", [])

    notes_summary = grading.get("user_notes_summary", {})
    notes = []
    notes.extend(notes_summary.get("uncertainties", []))
    notes.extend(notes_summary.get("needs_review", []))
    notes.extend(notes_summary.get("workarounds", []))
    result["notes"] = notes

    return result


def load_scenario_results(benchmark_dir: Path) -> dict:
    """Load eval-skills scenario-* results and unblind configs via label_key.json."""
    scenario_dirs = sorted(d for d in benchmark_dir.glob("scenario-*") if d.is_dir())
    if not scenario_dirs:
        return {}

    label_key = load_json(benchmark_dir / "label_key.json", {})
    results: dict[str, list] = {}

    for idx, scenario_dir in enumerate(scenario_dirs, start=1):
        metadata = load_json(scenario_dir / "eval_metadata.json", {})
        eval_id = metadata.get("eval_id", metadata.get("id", idx))
        mapping = label_key.get(scenario_dir.name, {})

        for version_dir in version_dirs_for_scenario(scenario_dir, mapping):
            version_name = version_dir.name
            config = mapping.get(version_name, version_name)
            results.setdefault(config, [])

            for run_idx, run_dir in enumerate(run_dirs_for_version(version_dir), start=1):
                grading_file = run_dir / "grading.json"
                grading = load_json(grading_file)
                if grading is None:
                    print(f"Warning: grading.json not found or invalid in {run_dir}")
                    continue

                try:
                    run_number = int(run_dir.name.split("-")[1]) if run_dir.name.startswith("run-") else run_idx
                except (IndexError, ValueError):
                    run_number = run_idx

                results[config].append(result_from_run(eval_id, config, run_number, run_dir, grading))

    return results


def load_run_results(benchmark_dir: Path) -> dict:
    """
    Load all run results from a benchmark directory.

    Returns dict keyed by config name (e.g. "with_skill"/"without_skill",
    or "new_skill"/"old_skill"), each containing a list of run results.
    """
    scenario_results = load_scenario_results(benchmark_dir)
    if scenario_results:
        return scenario_results

    # Support legacy layouts: eval dirs directly under benchmark_dir, or under runs/
    runs_dir = benchmark_dir / "runs"
    if runs_dir.exists():
        search_dir = runs_dir
    elif list(benchmark_dir.glob("eval-*")):
        search_dir = benchmark_dir
    else:
        print(f"No eval directories found in {benchmark_dir} or {benchmark_dir / 'runs'}")
        return {}

    results: dict[str, list] = {}

    for eval_idx, eval_dir in enumerate(sorted(search_dir.glob("eval-*"))):
        metadata_path = eval_dir / "eval_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path) as mf:
                    eval_id = json.load(mf).get("eval_id", eval_idx)
            except (json.JSONDecodeError, OSError):
                eval_id = eval_idx
        else:
            try:
                eval_id = int(eval_dir.name.split("-")[1])
            except ValueError:
                eval_id = eval_idx

        # Discover config directories dynamically rather than hardcoding names
        for config_dir in sorted(eval_dir.iterdir()):
            if not config_dir.is_dir():
                continue
            # Skip non-config directories (inputs, outputs, etc.)
            if not list(config_dir.glob("run-*")):
                continue
            config = config_dir.name
            if config not in results:
                results[config] = []

            for run_dir in sorted(config_dir.glob("run-*")):
                run_number = int(run_dir.name.split("-")[1])
                grading_file = run_dir / "grading.json"

                if not grading_file.exists():
                    print(f"Warning: grading.json not found in {run_dir}")
                    continue

                grading = load_json(grading_file)
                if grading is None:
                    print(f"Warning: grading.json not found or invalid in {grading_file}")
                    continue

                result = result_from_run(eval_id, config, run_number, run_dir, grading)

                raw_expectations = result["expectations"]
                for exp in raw_expectations:
                    if "text" not in exp or "passed" not in exp:
                        print(f"Warning: expectation in {grading_file} missing required fields (text, passed, evidence): {exp}")

                results[config].append(result)

    return results


def aggregate_results(results: dict) -> dict:
    """
    Aggregate run results into summary statistics.

    Returns run_summary with stats for each configuration and delta.
    """
    run_summary = {}
    configs = list(results.keys())

    for config in configs:
        runs = results.get(config, [])

        if not runs:
            run_summary[config] = {
                "pass_rate": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "time_seconds": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "tokens": None,
                "errors": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "output_chars": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
            }
            continue

        pass_rates = [r["pass_rate"] for r in runs]
        times = [r["time_seconds"] for r in runs]
        tokens = [r["tokens"] for r in runs if isinstance(r.get("tokens"), (int, float))]
        errors = [r.get("errors", 0) for r in runs]
        output_chars = [r.get("output_chars", 0) for r in runs]

        run_summary[config] = {
            "pass_rate": calculate_stats(pass_rates),
            "time_seconds": calculate_stats(times),
            "tokens": calculate_stats(tokens) if tokens else None,
            "errors": calculate_stats(errors),
            "output_chars": calculate_stats(output_chars),
        }

    # Prefer the meaningful eval-skills delta: with_skill minus without_skill.
    if "with_skill" in run_summary and "without_skill" in run_summary:
        primary = run_summary.get("with_skill", {})
        baseline = run_summary.get("without_skill", {})
    else:
        return run_summary

    delta_pass_rate = primary.get("pass_rate", {}).get("mean", 0) - baseline.get("pass_rate", {}).get("mean", 0)
    delta_time = primary.get("time_seconds", {}).get("mean", 0) - baseline.get("time_seconds", {}).get("mean", 0)
    primary_tokens = primary.get("tokens") or {}
    baseline_tokens = baseline.get("tokens") or {}
    delta_tokens = primary_tokens.get("mean", 0) - baseline_tokens.get("mean", 0)
    delta_errors = primary.get("errors", {}).get("mean", 0) - baseline.get("errors", {}).get("mean", 0)

    run_summary["delta"] = {
        "pass_rate": f"{delta_pass_rate:+.2f}",
        "time_seconds": f"{delta_time:+.1f}",
        "tokens": f"{delta_tokens:+.0f}",
        "errors": f"{delta_errors:+.2f}",
    }

    return run_summary


def generate_benchmark(benchmark_dir: Path, skill_name: str = "", skill_path: str = "") -> dict:
    """
    Generate complete benchmark.json from run results.
    """
    results = load_run_results(benchmark_dir)
    run_summary = aggregate_results(results)

    # Build runs array for benchmark.json
    runs = []
    for config in results:
        for result in results[config]:
            runs.append({
                "eval_id": result["eval_id"],
                "configuration": config,
                "run_number": result["run_number"],
                "result": {
                    "pass_rate": result["pass_rate"],
                    "passed": result["passed"],
                    "failed": result["failed"],
                    "total": result["total"],
                    "time_seconds": result["time_seconds"],
                    "tokens": result.get("tokens"),
                    "tool_calls": result.get("tool_calls", 0),
                    "errors": result.get("errors", 0),
                    "output_chars": result.get("output_chars", 0),
                },
                "expectations": result["expectations"],
                "notes": result["notes"]
            })

    # Determine eval IDs from results
    eval_ids = sorted(set(
        r["eval_id"]
        for config in results.values()
        for r in config
    ))
    per_scenario_counts = Counter(
        (config, r["eval_id"])
        for config, config_results in results.items()
        for r in config_results
    )
    runs_per_configuration = max(per_scenario_counts.values(), default=0)

    benchmark = {
        "metadata": {
            "skill_name": skill_name or "<skill-name>",
            "skill_path": skill_path or "<path/to/skill>",
            "executor_model": "<model-name>",
            "analyzer_model": "<model-name>",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": eval_ids,
            "runs_per_configuration": runs_per_configuration
        },
        "runs": runs,
        "run_summary": run_summary,
        "notes": []  # To be filled by analyzer
    }

    return benchmark


def generate_markdown(benchmark: dict) -> str:
    """Generate human-readable benchmark.md from benchmark data."""
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]

    # Determine config names (excluding "delta")
    configs = [k for k in run_summary if k != "delta"]

    lines = [
        f"# Skill Benchmark: {metadata['skill_name']}",
        "",
        f"**Model**: {metadata['executor_model']}",
        f"**Date**: {metadata['timestamp']}",
        f"**Evals**: {', '.join(map(str, metadata['evals_run']))} ({metadata['runs_per_configuration']} runs each per configuration)",
        "",
        "## Summary",
        "",
        "| Configuration | Pass Rate | Time | Tokens | Errors |",
        "|---------------|-----------|------|--------|--------|",
    ]

    for config in configs:
        summary = run_summary.get(config, {})
        label = config.replace("_", " ").title()
        pass_rate = summary.get("pass_rate", {})
        time_seconds = summary.get("time_seconds", {})
        tokens = summary.get("tokens")
        token_text = (
            f"{tokens.get('mean', 0):.0f} ± {tokens.get('stddev', 0):.0f}"
            if tokens else "n/a"
        )
        errors = summary.get("errors", {})
        lines.append(
            f"| {label} | "
            f"{pass_rate.get('mean', 0)*100:.0f}% ± {pass_rate.get('stddev', 0)*100:.0f}% | "
            f"{time_seconds.get('mean', 0):.1f}s ± {time_seconds.get('stddev', 0):.1f}s | "
            f"{token_text} | {errors.get('mean', 0):.2f} ± {errors.get('stddev', 0):.2f} |"
        )

    delta = run_summary.get("delta")
    if delta:
        lines.extend([
            "",
            "Delta is computed as `with_skill - without_skill`.",
            "",
            f"- Pass rate: {delta.get('pass_rate', '—')}",
            f"- Time: {delta.get('time_seconds', '—')}s",
            f"- Tokens: {delta.get('tokens', '—')}",
            f"- Errors: {delta.get('errors', '—')}",
        ])

    # Notes section
    if benchmark.get("notes"):
        lines.extend([
            "",
            "## Notes",
            ""
        ])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate benchmark run results into summary statistics"
    )
    parser.add_argument(
        "benchmark_dir",
        type=Path,
        help="Path to the benchmark directory"
    )
    parser.add_argument(
        "--skill-name",
        default="",
        help="Name of the skill being benchmarked"
    )
    parser.add_argument(
        "--skill-path",
        default="",
        help="Path to the skill being benchmarked"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output path for benchmark.json (default: <benchmark_dir>/benchmark.json)"
    )

    args = parser.parse_args()

    if not args.benchmark_dir.exists():
        print(f"Directory not found: {args.benchmark_dir}")
        sys.exit(1)

    # Generate benchmark
    benchmark = generate_benchmark(args.benchmark_dir, args.skill_name, args.skill_path)

    # Determine output paths
    output_json = args.output or (args.benchmark_dir / "benchmark.json")
    output_md = output_json.with_suffix(".md")

    # Write benchmark.json
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(benchmark, f, indent=2)
    print(f"Generated: {output_json}")

    # Write benchmark.md
    markdown = generate_markdown(benchmark)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"Generated: {output_md}")

    # Print summary
    run_summary = benchmark["run_summary"]
    configs = [k for k in run_summary if k != "delta"]
    delta = run_summary.get("delta", {})

    print(f"\nSummary:")
    for config in configs:
        pr = run_summary[config]["pass_rate"]["mean"]
        label = config.replace("_", " ").title()
        print(f"  {label}: {pr*100:.1f}% pass rate")
    print(f"  Delta:         {delta.get('pass_rate', '—')}")


if __name__ == "__main__":
    main()
