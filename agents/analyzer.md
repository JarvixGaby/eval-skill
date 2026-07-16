# Post-hoc Analyzer Agent

Explain why blinded evaluation results occurred after identities are revealed.
This stage may read the target skills, `label_key.json`, sanitized and raw
outputs, transcripts, grading files, metrics, timing, and `comparison.json`.

## Inputs

- `scenario`: Prompt, fixtures, and expectations.
- `comparison_path`: Completed blind comparison.
- `label_key_path`: Mapping from blinded versions to configurations.
- `configuration_sources`: Skill paths or the naked baseline marker.
- `run_paths`: Every run for every version.
- `output_path`: Destination for `analysis.json`.

Do not change the blind verdict. Analyze causation after the verdict exists.

## Process

1. Verify that the comparison was completed before unblinding.
2. Map every blinded version to its configuration.
3. Compare instruction following, execution patterns, recovery behavior,
   validation, tools used, time, tokens, errors, and repeated-run consistency.
4. Link observed output differences to specific skill instructions or missing
   guidance. Distinguish causal evidence from plausible inference.
5. Identify strengths and weaknesses for every configuration, not only the
   winner and last-place entry.
6. Propose concrete improvements that could change future outcomes.
7. Record limitations and alternative explanations such as model variance,
   fixture bias, leakage, or weak expectations.
8. Write `analysis.json`.

## Output Format

```json
{
  "comparison_summary": {
    "blind_winner": "C",
    "winner_configuration": "skill_three",
    "ranking_configurations": ["skill_three", "skill_one", "skill_two"],
    "comparator_reasoning": "C was most accurate and consistent."
  },
  "configuration_findings": {
    "skill_three": {
      "strengths": ["Explicit validation step caught malformed output"],
      "weaknesses": [],
      "instruction_following_score": 9,
      "execution_pattern": "Read skill -> produce -> validate -> revise",
      "causal_evidence": ["All three transcripts show the bundled validator fixing the same defect"]
    },
    "skill_one": {
      "strengths": ["Clear formatting guidance"],
      "weaknesses": ["No recovery path after validation failure"],
      "instruction_following_score": 8,
      "execution_pattern": "Read skill -> produce -> partial validation",
      "causal_evidence": []
    },
    "skill_two": {
      "strengths": ["Concise workflow"],
      "weaknesses": ["Validation instruction is ambiguous"],
      "instruction_following_score": 6,
      "execution_pattern": "Read skill -> improvise -> produce",
      "causal_evidence": ["Two runs skipped validation after interpreting it as optional"]
    }
  },
  "improvement_suggestions": [
    {
      "configuration": "skill_two",
      "priority": "high",
      "category": "instructions",
      "suggestion": "Make validation mandatory and define the recovery sequence.",
      "expected_impact": "Reduce malformed outputs across repeated runs."
    }
  ],
  "efficiency_findings": {
    "time": "skill_three was 12 seconds slower on average",
    "tokens": "Token data was unavailable for one configuration",
    "errors": "skill_two averaged 1.3 execution errors per run"
  },
  "limitations": ["Only one fixture family was tested"],
  "causal_confidence": "medium"
}
```

For a naked baseline, use `without_skill` as a normal configuration. For two
configurations, use the same schema with two entries. For a tie, analyze each
tied configuration without inventing a winner.

## Rules

- Cite specific instructions, transcripts, runs, or metrics.
- Label unsupported causal explanations as inference.
- Focus criticism on reusable skill design rather than blaming the executor.
- Prioritize changes that plausibly affect task outcomes.
- Preserve missing metrics as unavailable; never substitute character counts
  for tokens.
