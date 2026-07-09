# JSON Schemas (eval-skills)

This skill uses a scenario-first workspace inside `<workspace>/temp/`. Reused
files such as `grading.json`, `metrics.json`, `timing.json`, `comparison.json`,
`analysis.json`, and `benchmark.json` follow the base shapes in
`schemas_base.md` unless extended below.

## Workspace Layout

```text
<skill-name>-eval-workspace/
├── temp/
│   ├── target_skill_source.json
│   ├── target-skill/
│   ├── target-skills/
│   │   ├── skill_one/
│   │   └── skill_two/
│   ├── skill_profile.json
│   ├── scenario_set.json
│   ├── evaluation_context.json
│   ├── label_key.json
│   ├── fixtures/
│   ├── scenario-<id>/
│   │   ├── eval_metadata.json
│   │   ├── version_a/
│   │   │   ├── run-1/
│   │   │   │   ├── raw_outputs/
│   │   │   │   ├── outputs/
│   │   │   │   ├── transcript.md
│   │   │   │   ├── timing.json
│   │   │   │   ├── metrics.json
│   │   │   │   └── grading.json
│   │   │   └── run-2/
│   │   ├── version_b/
│   │   │   └── run-1/
│   │   ├── version_c/                  # optional for 3+ configurations
│   │   │   └── run-1/
│   │   ├── comparison.json
│   │   └── analysis.json
│   ├── benchmark.json
│   └── benchmark.md
└── comparison_report.html
```

Keep scratch scripts, downloaded archives, cloned repositories, generated
fixtures, renderer outputs, and benchmark JSON/Markdown under `temp/`. Put the
final static report at `<workspace>/comparison_report.html` so the user has one
stable file to open.

## skill_profile.json

Produced by `scripts/analyze_skill.py`, then corrected by the evaluator.

```json
{
  "skill_name": "pdf",
  "skill_path": "/path/to/pdf",
  "description": "Use for PDF creation and editing...",
  "domain_hint": "PDF creation, editing, form-filling, merging",
  "body_line_count": 340,
  "bundled_resources": {
    "scripts": ["scripts/fill_form.py"],
    "references": ["references/forms.md"],
    "assets": []
  },
  "has_bundled_scripts": true,
  "candidate_steps_detected": ["Inspect PDF", "Fill fields", "Validate"],
  "suggested_type": "procedural",
  "skill_type": "procedural",
  "capability_areas": ["fill PDF forms", "merge PDFs", "extract text"],
  "side_effect_risk": "local_write",
  "visual_output_types": ["pdf", "text"],
  "note": "heuristic output corrected by evaluator"
}
```

Valid `side_effect_risk` values: `read_only`, `local_write`, `external_read`,
`external_write`.

## target_skill_source.json

Records where the target came from and how it was isolated. For a baseline
comparison, a single target object is enough. For multi-skill comparisons, use
`targets` keyed by configuration name.

```json
{
  "source_type": "github",
  "source": "https://github.com/example/skills/tree/main/pdf",
  "install_method": "cloned into workspace temp/target-skill/",
  "resolved_path": "temp/target-skill/",
  "isolation_mode": "artifact_path",
  "global_install_detected": false,
  "baseline_skill_availability": "target skill not visible to baseline executor",
  "notes": []
}
```

Multi-skill example:

```json
{
  "targets": {
    "skill_one": {
      "source_type": "local_directory",
      "source": "/path/to/skill-one",
      "install_method": "copied into temp/target-skills/skill_one/",
      "resolved_path": "temp/target-skills/skill_one/",
      "isolation_mode": "artifact_path"
    },
    "skill_two": {
      "source_type": "local_directory",
      "source": "/path/to/skill-two",
      "install_method": "copied into temp/target-skills/skill_two/",
      "resolved_path": "temp/target-skills/skill_two/",
      "isolation_mode": "artifact_path"
    }
  },
  "notes": []
}
```

Valid `source_type` values include `skill_archive`, `local_directory`, `github`,
`install_command`, `pasted_files`, and `already_installed`.

Valid `isolation_mode` values:

- `artifact_path`: target is an inert local artifact; only with-skill receives its path
- `isolated_install`: target installed in a temporary skill root or separate agent environment
- `platform_denylist`: platform provides a verified per-run allowlist/denylist
- `current_environment`: target may be visible globally; baseline contamination risk is high

## scenario_set.json

Written after scenario brainstorming.

```json
{
  "skill_name": "pdf",
  "skill_type": "procedural",
  "scenario_strategy": {
    "coverage_goal": "cover fill forms, extraction, and validation",
    "scenario_count_reason": "medium skill; one scenario per major capability plus one edge case"
  },
  "steps": [
    {"id": 1, "label": "Inspect", "verifiable_signal": "lists fields and page count"},
    {"id": 2, "label": "Produce output", "verifiable_signal": "final artifact exists"},
    {"id": 3, "label": "Validate", "verifiable_signal": "reports blank fields or errors"}
  ],
  "scenarios": [
    {
      "id": 1,
      "theme": "small business W-9 form fill",
      "capability_area": "fill PDF forms",
      "prompt": "hey can you fill this W-9 for Acme Consulting LLC...",
      "files": ["temp/fixtures/w9_blank.pdf"],
      "expected_steps_touched": [1, 2, 3],
      "expected_visual_artifacts": ["pdf"],
      "expectations": [
        {
          "id": "requested_fields_filled",
          "type": "judge",
          "text": "The output PDF has all requested fields filled accurately"
        },
        {
          "id": "ein_format",
          "type": "programmatic",
          "text": "The EIN is formatted as 12-3456789",
          "check": "scripts/check_pdf_text.py"
        }
      ],
      "fixture_notes": "Synthetic blank W-9 stored under temp/fixtures/"
    }
  ]
}
```

Expectation `type` may be `programmatic` or `judge`. Use programmatic checks
when practical, especially for file existence, field values, schema validity,
links, calculations, and exact text.

## evaluation_context.json

Records evidence strength and execution safety.

```json
{
  "sampling_mode": "standard",
  "runs_per_configuration": 3,
  "blind_level": "strong_blind",
  "isolation_mode": "artifact_path",
  "baseline_contamination_risk": "low",
  "side_effect_risk": "local_write",
  "side_effect_mode": "sandbox",
  "artifact_leakage_risk": "low",
  "visual_comparability": "high",
  "visual_artifact_notes": "PPTX outputs include slide PNG previews",
  "limitations": [
    "No external-write scenarios were run"
  ]
}
```

Valid `blind_level` values:

- `strong_blind`: independent execution and judging agents
- `weak_blind`: isolated artifacts, but one orchestrator
- `not_blind`: same agent/conversation executed and judged

Valid `sampling_mode` value: `standard`. Use `runs_per_configuration: 3`.

Valid `baseline_contamination_risk`, `artifact_leakage_risk`, and
`visual_comparability` values: `low`, `medium`, `high`. For
`visual_comparability`, `high` means the primary outputs are embedded inline or
have neutral previews; `low` means the report mostly links to downloads.

## label_key.json

Written before execution and hidden from blind judges.

```json
{
  "scenario-1": {"version_a": "without_skill", "version_b": "with_skill"},
  "scenario-2": {"version_a": "with_skill", "version_b": "without_skill"}
}
```

For comparing two skills without a naked baseline, map versions to configuration
names:

```json
{
  "scenario-1": {"version_a": "skill_one", "version_b": "skill_two"},
  "scenario-2": {"version_a": "skill_two", "version_b": "skill_one"}
}
```

For three or more configurations, add `version_c`, `version_d`, and so on.
Assignments should be randomized per scenario. Do not use predictable
alternation unless recording that limitation in `evaluation_context.json`.

## PPTX Preview Convention

When a run produces `deck.pptx`, include one or more neutral preview files in
the same `outputs/` directory:

```text
deck.pptx
deck.preview-01.png
deck.preview-02.png
deck.preview.pdf
```

The report generator embeds preview images/PDFs and provides a download link for
the original `.pptx`. It does not require a specific PPTX renderer.
