# eval-skills

[中文文档](./README.zh-CN.md)

`eval-skills` is an agent skill for evaluating whether another reusable agent
skill actually improves outcomes. It turns a target skill into a small benchmark:
realistic scenarios, with-skill vs baseline runs, graded outputs, aggregate
metrics, and one side-by-side HTML report.

The goal is not to prove a skill's claims. The goal is to answer a practical
question: "Does this skill help on realistic tasks compared with asking the
agent directly?"

## Installation

### Ask An Agent To Install It

Send this to an agent with shell access:

```text
Install the eval-skills agent skill from:
https://github.com/JarvixGaby/eval-skill

Please clone it into my agent skills directory as eval-skills, then verify that
SKILL.md, README.md, agents/, references/, and scripts/ exist.
```

For Codex-style local skills, the target directory is usually:

```bash
~/.codex/skills/eval-skills
```

For Claude-style local skills, the target directory is usually:

```bash
~/.claude/skills/eval-skills
```

### Manual Install

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/JarvixGaby/eval-skill ~/.codex/skills/eval-skills
```

If you use a different agent, place this repository in that agent's skill
directory. The repository root should contain `SKILL.md`.

## How To Use

Ask your agent to use `eval-skills` and provide the target skill source.

Example:

```text
Use eval-skills to evaluate https://github.com/example/example-skill.
```

You can provide any of these as the target:

- A GitHub repository URL.
- A local skill directory.
- A `.skill` archive.
- A documented install command.
- Pasted `SKILL.md` content plus referenced files.

The user usually only needs to provide:

- The target skill source.
- Any constraints on what should or should not be tested.
- Any real input files that matter for the skill, if available.
- Whether external side effects are allowed. By default, they are not.

The skill will then:

1. Copy or clone the target into `temp/target-skill/`.
2. Read the target skill and classify its capability areas.
3. Generate realistic scenario prompts from the target skill's actual use cases.
4. Run each scenario with the skill and without the skill.
5. Grade every run.
6. Compare blinded Version A vs Version B.
7. Aggregate results.
8. Produce `comparison_report.html`.

## Standard Evaluation Mode

`eval-skills` uses one standard sampling mode:

```json
{
  "sampling_mode": "standard",
  "runs_per_configuration": 3
}
```

Each scenario is run:

- 3 times with the target skill.
- 3 times without the target skill.

The HTML report shows all three runs for Version A and all three runs for
Version B. It must not hide failed runs, show only the best run, or replace
real outputs with an average summary.

## Directory Structure

Publish this repository with the following files:

```text
eval-skills/
├── SKILL.md
├── README.md
├── README.zh-CN.md
├── .gitignore
├── agents/
│   ├── analyzer.md
│   ├── comparator.md
│   └── grader.md
├── references/
│   ├── schemas.md
│   └── schemas_base.md
├── scripts/
│   ├── __init__.py
│   ├── analyze_skill.py
│   ├── aggregate_benchmark.py
│   ├── generate_comparison_report.py
│   ├── utils.py
│   └── validate_workspace.py
└── eval-viewer/
    ├── generate_review.py
    └── viewer.html
```

Generated evaluation files are kept out of the repository. A normal run creates:

```text
<workspace>/
├── temp/
│   ├── target-skill/
│   ├── target_skill_source.json
│   ├── skill_profile.json
│   ├── scenario_set.json
│   ├── evaluation_context.json
│   ├── label_key.json
│   ├── scenario-1/
│   │   ├── version_a/run-1/
│   │   ├── version_a/run-2/
│   │   ├── version_a/run-3/
│   │   ├── version_b/run-1/
│   │   ├── version_b/run-2/
│   │   └── version_b/run-3/
│   ├── benchmark.json
│   └── benchmark.md
└── comparison_report.html
```

Do not commit generated artifacts:

```text
temp/
comparison_report.html
benchmark.json
benchmark.md
scenario-*/
target-skill/
__pycache__/
.DS_Store
node_modules/
```

## Core Advantages

- **Baseline comparison first**: the target skill is compared against a baseline
  agent that receives only the task prompt.
- **Scenario generation from the skill itself**: prompts are derived from the
  target skill's description, workflow, and likely real use cases.
- **Isolated target skill**: the target is kept as a local artifact by default,
  reducing contamination of the baseline run.
- **Standard 3-run sampling**: repeated runs make failures and variance visible.
- **Workspace validation**: `validate_workspace.py` catches missing run files,
  incomplete scenario folders, and non-standard sampling metadata before report
  generation.
- **Side-by-side report**: final artifacts are embedded in one static HTML file
  for direct comparison.
- **Honest evidence labels**: the workflow records blind level, side-effect risk,
  leakage risk, and limitations.
- **Clean workspace**: all working files go into `temp/`; the final report stays
  at the workspace root.

## How It Works

`eval-skills` treats a skill as a black-box product.

1. **Acquire and isolate**  
   The target skill is cloned or copied into `temp/target-skill/`. It is not
   installed globally by default, because global installation can contaminate the
   baseline.

2. **Analyze the target**  
   `scripts/analyze_skill.py` reads `SKILL.md` and bundled resources to produce a
   first-pass `skill_profile.json`. The agent still reads the skill directly and
   corrects the profile when needed.

3. **Generate scenarios**  
   The agent creates realistic tasks from the target skill's claimed use cases.
   The prompts are designed to naturally hit the skill's intended trigger
   surface, so a separate trigger test is not run by default.

4. **Run with and without the skill**  
   For each scenario, Version A and Version B are assigned randomly. One version
   uses the skill path; the other receives only the task prompt and fixtures.

5. **Sanitize and grade**  
   Final user-visible outputs are copied into `outputs/`. Scratch traces stay in
   `raw_outputs/`. Each run is graded against the scenario expectations.

6. **Compare and unblind**  
   A comparator judges Version A vs Version B from sanitized outputs. After that,
   the evaluation is unblinded for analysis.

7. **Validate, aggregate, report**  
   The workspace is validated, benchmark metrics are aggregated, and a static
   `comparison_report.html` is generated.

## Helper Commands

Analyze a target skill:

```bash
python3 scripts/analyze_skill.py <workspace>/temp/target-skill \
  --out <workspace>/temp/skill_profile.json
```

Validate a completed workspace:

```bash
python3 scripts/validate_workspace.py <workspace>/temp
```

Aggregate benchmark metrics:

```bash
python3 scripts/aggregate_benchmark.py <workspace>/temp \
  --skill-name <skill-name>
```

Generate the HTML report:

```bash
python3 scripts/generate_comparison_report.py <workspace>/temp \
  --skill-name <skill-name> \
  --out <workspace>/comparison_report.html
```

## Notes

- The default mode avoids external side effects. If a target skill sends email,
  deploys software, writes to SaaS systems, purchases items, deletes data, or
  changes real-world state, use sandbox or dry-run scenarios unless the user
  explicitly approves live actions.
- This skill measures evidence strength, not certainty. A report should state
  its blind level, limitations, and residual risks.
- The final report is static HTML and can be opened locally or shared as an
  artifact.

