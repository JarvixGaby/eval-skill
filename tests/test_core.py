import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import aggregate_benchmark
import analyze_skill
import generate_comparison_report
import validate_workspace


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


review = load_module("eval_review", ROOT / "eval-viewer" / "generate_review.py")


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def make_workspace(base: Path, versions=("version_a", "version_b", "version_c")) -> Path:
    workspace = base / "temp"
    workspace.mkdir()
    write_json(workspace / "target_skill_source.json", {"targets": {}})
    write_json(workspace / "skill_profile.json", {"skill_name": "demo"})
    write_json(
        workspace / "scenario_set.json",
        {
            "scenarios": [
                {
                    "id": 1,
                    "prompt": "Create a safe report",
                    "expectations": [
                        {"id": "safe", "type": "judge", "text": "No unsafe HTML"}
                    ],
                }
            ]
        },
    )
    write_json(
        workspace / "evaluation_context.json",
        {
            "sampling_mode": "standard",
            "runs_per_configuration": 3,
            "blind_level": "strong_blind",
            "baseline_contamination_risk": "low",
            "artifact_leakage_risk": "low",
            "visual_comparability": "high",
            "isolation_mode": "artifact_path",
            "side_effect_risk": "local_write",
        },
    )
    mapping = {version: f"config_{index}" for index, version in enumerate(versions)}
    write_json(workspace / "label_key.json", {"scenario-1": mapping})
    scenario = workspace / "scenario-1"
    write_json(
        scenario / "eval_metadata.json",
        {"eval_id": 1, "eval_name": "Safety", "prompt": "Create a safe report"},
    )
    labels = [version.removeprefix("version_").upper() for version in versions]
    write_json(
        scenario / "comparison.json",
        {
            "method": "n_way",
            "versions_compared": labels,
            "winner": labels[-1],
            "ranking": list(reversed(labels)),
            "ties": [],
            "reasoning": "Most consistent",
            "output_quality": {label: {"score": 8} for label in labels},
        },
    )
    write_json(
        scenario / "analysis.json",
        {
            "configuration_findings": {
                mapping[versions[-1]]: {
                    "strengths": ["Validated output"],
                    "weaknesses": [],
                }
            },
            "improvement_suggestions": [],
        },
    )
    for version_index, version in enumerate(versions):
        for run_number in range(1, 4):
            run = scenario / version / f"run-{run_number}"
            (run / "outputs").mkdir(parents=True)
            (run / "raw_outputs").mkdir()
            (run / "outputs" / "result.txt").write_text("ok", encoding="utf-8")
            (run / "transcript.md").write_text("done", encoding="utf-8")
            write_json(
                run / "timing.json",
                {
                    "total_duration_seconds": 10 + version_index,
                    "total_tokens": 100 + run_number,
                },
            )
            write_json(
                run / "metrics.json",
                {"total_tool_calls": 2, "errors_encountered": version_index, "output_chars": 9999},
            )
            write_json(
                run / "grading.json",
                {
                    "summary": {"pass_rate": 1.0, "passed": 1, "failed": 0, "total": 1},
                    "timing": {"total_duration_seconds": 999},
                    "execution_metrics": {"output_chars": 7777},
                    "expectations": [{"text": "No unsafe HTML", "passed": True, "evidence": "ok"}],
                },
            )
    return workspace


class CoreTests(unittest.TestCase):
    def test_analyzer_ignores_generated_files(self):
        with tempfile.TemporaryDirectory() as td:
            skill = Path(td)
            (skill / "scripts" / "__pycache__").mkdir(parents=True)
            (skill / "scripts" / "tool.py").write_text("", encoding="utf-8")
            (skill / "scripts" / "__pycache__" / "tool.pyc").write_bytes(b"x")
            resources = analyze_skill.find_bundled_resources(skill)
            self.assertEqual(resources["scripts"], ["scripts/tool.py"])
            self.assertEqual(resources["assets"], [])

    def test_aggregate_uses_real_tokens_and_three_runs(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = make_workspace(Path(td))
            benchmark = aggregate_benchmark.generate_benchmark(workspace, "demo")
            self.assertEqual(benchmark["metadata"]["runs_per_configuration"], 3)
            self.assertAlmostEqual(benchmark["run_summary"]["config_0"]["tokens"]["mean"], 102)
            self.assertEqual(benchmark["run_summary"]["config_0"]["time_seconds"]["mean"], 10)
            self.assertEqual(benchmark["run_summary"]["config_1"]["errors"]["mean"], 1)
            self.assertNotEqual(benchmark["run_summary"]["config_0"]["tokens"]["mean"], 9999)

    def test_missing_tokens_remain_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            write_json(run / "timing.json", {"total_duration_seconds": 3})
            write_json(run / "metrics.json", {"output_chars": 5000})
            result = aggregate_benchmark.result_from_run(
                1,
                "with_skill",
                1,
                run,
                {"summary": {"pass_rate": 1, "passed": 1, "failed": 0, "total": 1}},
            )
            self.assertIsNone(result["tokens"])
            self.assertEqual(result["output_chars"], 5000)

    def test_common_duration_seconds_is_supported(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            write_json(run / "timing.json", {"duration_seconds": 17, "token_usage": 250})
            result = aggregate_benchmark.result_from_run(
                1,
                "with_skill",
                1,
                run,
                {"summary": {"pass_rate": 1, "passed": 1, "failed": 0, "total": 1}},
            )
            self.assertEqual(result["time_seconds"], 17)
            self.assertEqual(result["tokens"], 250)

    def test_validator_accepts_three_versions(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = make_workspace(Path(td))
            errors, warnings = validate_workspace.validate(workspace)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_report_contains_expectations_metrics_analysis_and_escaped_filename(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            workspace = make_workspace(base)
            benchmark = aggregate_benchmark.generate_benchmark(workspace, "demo")
            write_json(workspace / "benchmark.json", benchmark)
            malicious = workspace / "scenario-1" / "version_a" / "run-1" / "outputs" / '<img src=x onerror=alert(1)>.txt'
            malicious.write_text("safe", encoding="utf-8")
            out = base / "report.html"
            old_argv = sys.argv
            try:
                sys.argv = ["report", str(workspace), "--skill-name", "demo", "--out", str(out)]
                generate_comparison_report.main()
            finally:
                sys.argv = old_argv
            html = out.read_text(encoding="utf-8")
            self.assertIn("No unsafe HTML", html)
            self.assertIn("Validated output", html)
            self.assertIn("Configuration", html)
            self.assertIn("&lt;img src=x onerror=alert(1)&gt;.txt", html)
            self.assertNotIn('<div class="file-name"><img src=x', html)

    def test_viewer_escapes_script_terminator(self):
        html = review.generate_html(
            [{"id": "1", "prompt": "</script><script>alert(1)</script>", "outputs": [], "grading": None}],
            "demo",
        )
        self.assertNotIn("</script><script>alert(1)</script>", html)
        self.assertIn("\\u003c/script", html)


if __name__ == "__main__":
    unittest.main()
