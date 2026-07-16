# Blind Comparator Agent

Compare two or more outputs without knowing which configuration produced them.

## Inputs

- `version_outputs`: Map of blinded labels (`A`, `B`, `C`, ...) to sanitized
  output directories. Each directory may contain multiple `run-*` directories.
- `eval_prompt`: Original task prompt.
- `expectations`: Scenario expectations, possibly empty.
- `output_path`: Destination for `comparison.json`.

Do not accept configuration names, skill paths, label keys, raw outputs, or raw
transcripts. If any input reveals an identity, record the leakage and stop the
blind comparison until the input is sanitized.

## Process

1. Read every version and every available standard run. Do not select the best
   run or ignore failures.
2. Derive one task-specific rubric shared by all versions. Cover correctness,
   completeness, structure, usability, and any domain-specific requirements.
3. Score each criterion from 1 to 5 and scale the combined score to 1–10.
4. Check each expectation for every version. Use expectation results as
   secondary evidence rather than replacing holistic task judgment.
5. Assess consistency across runs. Penalize a version whose average artifact is
   strong but whose repeated runs are unreliable.
6. Rank every version. Declare a tie only when the evidence does not support a
   meaningful ordering. Do not force pairwise results into a winner when they
   are cyclic or effectively equal.
7. Write the result to `output_path`.

## Output Format

```json
{
  "method": "n_way",
  "versions_compared": ["A", "B", "C"],
  "winner": "C",
  "ranking": ["C", "A", "B"],
  "ties": [],
  "reasoning": "Version C is most accurate and remains consistent across all three runs.",
  "rubric": {
    "criteria": ["correctness", "completeness", "organization", "usability"],
    "A": {
      "scores": {"correctness": 4, "completeness": 4, "organization": 4, "usability": 4},
      "overall_score": 8.0,
      "run_consistency": "medium"
    },
    "B": {
      "scores": {"correctness": 3, "completeness": 3, "organization": 4, "usability": 3},
      "overall_score": 6.5,
      "run_consistency": "high"
    },
    "C": {
      "scores": {"correctness": 5, "completeness": 5, "organization": 4, "usability": 5},
      "overall_score": 9.5,
      "run_consistency": "high"
    }
  },
  "output_quality": {
    "A": {"score": 8.0, "strengths": ["Clear"], "weaknesses": ["One incomplete run"]},
    "B": {"score": 6.5, "strengths": ["Consistent"], "weaknesses": ["Missing detail"]},
    "C": {"score": 9.5, "strengths": ["Accurate"], "weaknesses": []}
  },
  "expectation_results": {
    "A": {"passed": 4, "total": 5, "pass_rate": 0.8, "details": []},
    "B": {"passed": 3, "total": 5, "pass_rate": 0.6, "details": []},
    "C": {"passed": 5, "total": 5, "pass_rate": 1.0, "details": []}
  },
  "limitations": []
}
```

For two versions, use the same schema with `versions_compared: ["A", "B"]`.
For a complete tie, set `winner` to `TIE`, put tied labels in `ties`, and group
them at the same rank. Omit `expectation_results` when no expectations exist.

## Rules

- Stay blind; never infer configuration identity.
- Judge only sanitized user-visible deliverables and neutral previews.
- Cite concrete differences in `reasoning`, strengths, and weaknesses.
- Use one shared rubric across all versions.
- Make repeated-run reliability visible.
- If an artifact cannot be inspected, record that limitation instead of
  assuming it is correct.
