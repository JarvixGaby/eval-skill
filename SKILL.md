---
name: eval-skills
description: Evaluate, benchmark, or test-drive an unfamiliar AI agent skill, tool bundle, prompt workflow, or capability package. Use when the user asks whether a downloaded/shared .skill, SKILL.md, agent workflow, or reusable AI capability actually helps, is worth installing, works as advertised, or performs better than asking an agent directly. This skill generates realistic scenarios from the target capability, runs with-capability vs baseline comparisons, records evidence strength, controls for leakage and side effects, and produces a side-by-side HTML report.
---

# Eval Skills

Evaluate an AI agent capability as a black-box product: does it improve real
task outcomes compared with a baseline agent that receives only the task prompt?

This skill is for evaluators, not authors. The evaluator may not know the target
domain well, so this workflow supplies scenario generation, evidence collection,
comparison, confidence labeling, and a user-readable HTML report.

Use the word "skill" below to mean any reusable agent capability: a Codex skill,
Claude skill, prompt workflow, tool bundle, MCP-backed agent, or similar package.

## Core Principles

- Compare the target skill against a baseline, not against its own claims.
- Keep the user's workspace tidy. Put all evaluation working files under a
  single `<workspace>/temp/` directory, including cloned target skills,
  fixtures, scenario folders, raw outputs, transcripts, intermediate JSON,
  benchmarks, and scratch scripts. The only files that should normally live
  outside `temp/` are the final `comparison_report.html` and, if useful, a
  short README or index that points to it.
- Keep the target skill out of the evaluator's global skill registry by default.
  A baseline is contaminated if the target skill can auto-trigger there.
- Generate realistic scenarios by reading the target skill and brainstorming its
  likely use cases; do not require the user to invent scenarios.
- State evidence strength honestly. A single-agent sequential run is not truly
  blind, even if labels are hidden in the report.
- Keep judging inputs clean. The judge should see final deliverables and neutral
  previews, not tool-specific scratch files that reveal which side used the skill.
- Avoid real-world side effects unless the user explicitly approves them.
- Produce one static HTML report that embeds the important artifacts inline when
  practical. Images, text, HTML, PDFs, and PPTX previews are primary report types.

## Workflow

### 1. Acquire And Isolate The Target Skill

Start from the user's installation source, not from an already-active global
skill whenever possible. Accept:

- a `.skill` archive
- a local skill directory
- a GitHub URL or repository path
- a documented install command
- pasted SKILL.md content plus referenced files

Install, clone, unpack, or copy the target into the eval workspace, for example:

```text
<workspace>/temp/target-skill/
```

Before creating any evaluation artifact, create `<workspace>/temp/` and treat it
as the benchmark workspace. Do not scatter `scenario-*`, `fixtures/`,
`target-skill/`, `benchmark.json`, helper scripts, or rendered test outputs in
the repository root.

Do not install the target skill into the evaluator's global skill root just to
run the A/B test. If it is globally installed, the baseline can still auto-trigger
it, even from another git branch or worktree. Branches and worktrees isolate files,
not the agent's available skill list.

Use one of these isolation modes:

- **`artifact_path`**: default. Keep the target as an inert local artifact. The
  `with_skill` executor receives `Skill path: <workspace>/temp/target-skill`; the
  `without_skill` executor receives only the task prompt and fixtures.
- **`isolated_install`**: install into a temporary skill root or separate agent
  environment. Use this when testing installed-skill behavior or auto-triggering.
- **`platform_denylist`**: use only if the platform provides a verifiable per-run
  skill allowlist/denylist. Soft instructions like "do not use this skill" are
  not enough.
- **`current_environment`**: last resort. Use only when the target is already
  active and cannot be isolated. Mark `baseline_contamination_risk` as `high`.

Write `<workspace>/temp/target_skill_source.json` with the source, install
method, resolved local path, and isolation mode.

Do not run a dedicated auto-trigger test by default. The scenario prompts should
be generated from the target skill's actual description and use cases, so they
should naturally exercise the skill's intended trigger surface while the
evaluation remains focused on output quality.

### 2. Analyze Target And Risk

Run the deterministic scaffold:

```bash
python -m scripts.analyze_skill <path-to-skill> --out <workspace>/temp/skill_profile.json
```

Then read the target skill's main instructions yourself and update
`skill_profile.json` if needed.

Classify:

- **skill_type**
  - `procedural`: ordered stages produce checkable intermediate artifacts.
  - `holistic`: style, judgment, or domain knowledge with no fixed sequence.
- **capability_areas**: the major things the skill claims to do. Broad skills
  need more scenarios than narrow skills.
- **side_effect_risk**
  - `read_only`: analysis or local inspection only.
  - `local_write`: creates local files only.
  - `external_read`: reads external systems.
  - `external_write`: writes external systems, sends messages, changes records,
    deploys, purchases, deletes, or otherwise affects real state.
- **visual_output_types**: expected deliverables such as text, HTML, images,
  PDF, PPTX, DOCX, XLSX, JSON, or code.

If `side_effect_risk` is `external_write`, do not run live tasks by default.
Switch to dry-run/sandbox scenarios or ask the user before executing anything
that could affect real systems.

### 3. Generate Scenarios And Fixtures

Generate scenarios from the target skill's actual use cases. The method is
brainstorming plus judgment, not a fixed template.

Choose scenario count by scope:

- narrow skill: 2-3 scenarios
- medium skill: 4-6 scenarios
- broad skill: cover the main capability areas, usually 6-10 scenarios
- expensive or side-effect-sensitive skill: start with 1-2 dry-run smoke tests

Each scenario should include:

- a realistic user prompt, with concrete names, files, constraints, and casual
  phrasing where appropriate
- a distinct theme or capability area
- expected outputs and expectations
- needed input files, if any
- expected visual artifacts for the final report

For input files:

- Use files the user provides when available.
- Otherwise create synthetic fixtures locally under `<workspace>/temp/fixtures/`.
- If a fixture cannot be safely created, mark that capability as not covered.
- Do not download arbitrary external files unless the user approves or the source
  is clearly safe and necessary.

For PPTX outputs, require a preview artifact when possible. The executor should
save slide images or a PDF preview next to the `.pptx`, using names such as
`deck.preview-01.png`, `deck.preview-02.png`, or `deck.preview.pdf`. The report
generator embeds these previews inline and keeps the `.pptx` available for
download.

Save scenarios to `<workspace>/temp/scenario_set.json` using
`references/schemas.md`.
Show the scenario list to the user before running. Do not block indefinitely if
the user has already indicated they want execution to continue.

### 4. Plan Standard Sampling And Blinding

Use standard sampling for every evaluation:

- Run each scenario three times per configuration.
- Set `sampling_mode` to `standard`.
- Set `runs_per_configuration` to `3`.
- If a scenario is too expensive or unsafe to run three times per configuration,
  reduce the scenario count or narrow the task instead of switching modes.

Set `blind_level` honestly:

- `strong_blind`: independent executor agents and independent judge agents; the
  judge never sees `label_key.json`, raw transcripts, or skill-specific traces.
- `weak_blind`: one orchestrator coordinates isolated artifacts, but the judge
  only sees sanitized version A/B outputs.
- `not_blind`: one agent in one conversation executes and judges. Do not call
  the result a blind test; label it as self-comparison.

Create `<workspace>/temp/evaluation_context.json` with `sampling_mode:
"standard"`, `runs_per_configuration: 3`, `blind_level`, `isolation_mode`,
`baseline_contamination_risk`, `side_effect_risk`, and notes.

Create `<workspace>/temp/label_key.json` before execution. Randomize A/B
assignment per scenario with an explicit random source or script. Do not use
predictable alternation as the default.

### 5. Execute With And Without The Skill

For each scenario, run both configurations:

- `with_skill`: the executor receives the target skill path and should use it.
- `without_skill`: the executor receives only the task prompt and fixtures.

If the target skill is installed globally or visible in the baseline agent's
available skills, do not claim a clean baseline. Either switch to
`isolated_install` / `platform_denylist`, or record the limitation in
`evaluation_context.json`.

Save each run under:

```text
<workspace>/temp/scenario-<id>/version_a/run-<n>/
<workspace>/temp/scenario-<id>/version_b/run-<n>/
```

Each run directory should contain:

- `raw_outputs/`: all files the executor created
- `outputs/`: sanitized final deliverables and neutral previews for judging/reporting
- `transcript.md`: what happened
- `timing.json`: duration and token data when available
- `metrics.json`: tool calls, files, and errors when available

For procedural skills, include step files when they help comparison, using the
same names across A and B.

### 6. Sanitize Artifacts

Before judging, copy or rename user-visible deliverables into `outputs/`.

Remove or neutralize leakage:

- tool-specific scratch files
- filenames that reveal a bundled script or skill identity
- logs that mention the target skill
- raw transcripts
- metadata not visible to an actual user

Keep leaked/raw material in `raw_outputs/` for post-hoc analysis, not blind
judging. If leakage cannot be removed without losing the deliverable, set
`artifact_leakage_risk` to `medium` or `high` in `evaluation_context.json`.

### 7. Grade And Compare

Use `agents/grader.md` to grade each run against the scenario expectations.
Prefer programmatic checks when practical. Natural-language judging is acceptable
for subjective quality, but do not use it when a script can verify the outcome.

Use `agents/comparator.md` to compare sanitized Version A vs Version B per
scenario. The comparator must not see:

- `label_key.json`
- raw transcripts
- raw_outputs
- target skill path
- filenames or notes that reveal which side used the skill

After blind comparison, unblind and use `agents/analyzer.md` to explain why the
skill helped, failed, or made no difference. The analyzer may read transcripts,
raw outputs, and the target skill after the blind verdict exists.

### 8. Validate And Aggregate

Before aggregating, validate that the workspace has the required files and that
standard sampling metadata is consistent:

```bash
python -m scripts.validate_workspace <workspace>/temp
```

Fix validation errors before generating a report.

Run:

```bash
python -m scripts.aggregate_benchmark <workspace>/temp --skill-name <skill-name>
```

The aggregator reads the `scenario-*` layout and repeated `run-*` directories.
It computes pass-rate, time, token, and error summaries.

### 9. Generate The HTML Report

Run:

```bash
python -m scripts.generate_comparison_report <workspace>/temp --skill-name <skill-name> --out <workspace>/comparison_report.html
```

The report is the main deliverable. It should show:

- overall verdict and evidence strength
- blind level, sampling mode, run count, side-effect risk, and leakage risk
- isolation mode and baseline contamination risk
- each scenario's prompt and expectations
- Version A and Version B side by side
- all three standard runs for each version. Do not show only the best run, the
  first run, an average artifact, or a summary in place of the run outputs.
- inline images, text, HTML, PDFs, and PPTX previews when present
- download links for binary originals
- grading details and blind comparator reasoning
- reveal controls for A/B identity

If a result cannot be rendered inline, the report must say so rather than imply
the user can visually compare it in the page.

## Reference Files

- `references/schemas.md`: workspace JSON schemas and layout
- `agents/grader.md`: per-run expectation grader
- `agents/comparator.md`: blind A/B judge
- `agents/analyzer.md`: post-hoc explanation
- `scripts/analyze_skill.py`: first-pass skill profiler
- `scripts/validate_workspace.py`: workspace and schema sanity checks before aggregation
- `scripts/aggregate_benchmark.py`: benchmark aggregation
- `scripts/generate_comparison_report.py`: static side-by-side HTML report
- `eval-viewer/`: optional secondary per-run review UI
