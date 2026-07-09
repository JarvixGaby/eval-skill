#!/usr/bin/env python3
"""
Generate a side-by-side comparison HTML report for eval-skills.

Unlike skill-creator's eval-viewer (which shows one run at a time with
prev/next navigation -- built for iterative authoring, not A/B reading),
this produces a single static HTML file where, for each scenario, every
version renders in blinded columns ("Version A", "Version B", ...), with a
per-scenario reveal toggle and a top-level verdict card.

Usage:
    python generate_comparison_report.py <workspace>/temp --skill-name <name> --out <workspace>/comparison_report.html

Expects the eval-skills workspace layout:
    <workspace>/temp/scenario_set.json
    <workspace>/temp/label_key.json
    <workspace>/temp/scenario-<id>/eval_metadata.json
    <workspace>/temp/scenario-<id>/version_a/run-1..3/outputs/*  (+ grading.json, transcript.md)
    <workspace>/temp/scenario-<id>/version_b/run-1..3/outputs/*  (+ grading.json, transcript.md)
    <workspace>/temp/scenario-<id>/version_c/run-1..3/outputs/*  (optional)
    <workspace>/temp/scenario-<id>/comparison.json       (optional, blind judge verdict)
    <workspace>/temp/evaluation_context.json             (optional evidence-strength metadata)

No dependencies beyond the Python stdlib.
"""
import argparse
import base64
import json
import mimetypes
from pathlib import Path

TEXT_EXT = {".txt", ".md", ".json", ".csv", ".py", ".js", ".css"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
MIME_OVERRIDES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def mime_of(p: Path) -> str:
    return MIME_OVERRIDES.get(p.suffix.lower()) or mimetypes.guess_type(str(p))[0] or "application/octet-stream"


def escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def escape_attr(s: str) -> str:
    return escape(s).replace('"', "&quot;")


def data_download_link(p: Path, label: str = "Download") -> str:
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f'<a download="{escape_attr(p.name)}" href="data:{mime_of(p)};base64,{b64}">{escape(label)}</a>'


def pptx_preview_files(p: Path) -> list[Path]:
    patterns = [
        f"{p.stem}.preview*.png",
        f"{p.stem}.preview*.jpg",
        f"{p.stem}.preview*.jpeg",
        f"{p.stem}.preview*.webp",
        f"{p.stem}.preview*.pdf",
        f"{p.stem}-preview*.png",
        f"{p.stem}-preview*.pdf",
    ]
    previews: list[Path] = []
    for pattern in patterns:
        previews.extend(sorted(p.parent.glob(pattern)))
    return sorted(set(previews))


def is_office_preview_file(p: Path, all_files: list[Path]) -> bool:
    if ".preview" not in p.stem and "-preview" not in p.stem:
        return False
    prefixes = [f.stem for f in all_files if f.suffix.lower() == ".pptx"]
    return any(p.name.startswith(prefix) for prefix in prefixes)


def render_output_file(p: Path) -> str:
    ext = p.suffix.lower()
    if ext == ".pdf":
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return (f'<div class="file-block"><div class="file-name">{p.name}</div>'
                f'<embed src="data:application/pdf;base64,{b64}" type="application/pdf" class="pdf-embed"/></div>')
    if ext in IMAGE_EXT:
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return (f'<div class="file-block"><div class="file-name">{p.name}</div>'
                f'<img src="data:{mime_of(p)};base64,{b64}" class="img-embed"/></div>')
    if ext == ".html":
        text = p.read_text(errors="replace")
        return (f'<div class="file-block"><div class="file-name">{p.name}</div>'
                f'<iframe class="html-embed" sandbox srcdoc="{escape_attr(text)}"></iframe>'
                f'<details><summary>View source</summary><pre class="text-embed">{escape(text)}</pre></details></div>')
    if ext == ".pptx":
        previews = pptx_preview_files(p)
        preview_html = ""
        if previews:
            preview_html = ''.join(render_output_file(preview) for preview in previews)
        else:
            preview_html = '<div class="unsupported-note">No PPTX preview file found. Add deck.preview-01.png or deck.preview.pdf to embed slides inline.</div>'
        return (f'<div class="file-block"><div class="file-name">{p.name} (PPTX)</div>'
                f'{preview_html}<div class="download-link">{data_download_link(p, "Download original PPTX")}</div></div>')
    if ext in TEXT_EXT:
        text = p.read_text(errors="replace")
        return (f'<div class="file-block"><div class="file-name">{p.name}</div>'
                f'<pre class="text-embed">{escape(text)}</pre></div>')
    return (f'<div class="file-block"><div class="file-name">{p.name} (binary)</div>'
            f'{data_download_link(p)}</div>')


def load_json(p: Path, default=None):
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return default
    return default


def run_sort_key(p: Path) -> tuple[int, str]:
    try:
        return (int(p.name.split("-", 1)[1]), p.name)
    except (IndexError, ValueError):
        return (10**9, p.name)


def version_sort_key(p: Path) -> tuple[int, str]:
    suffix = p.name.removeprefix("version_")
    if len(suffix) == 1 and suffix.isalpha():
        return (ord(suffix.lower()) - ord("a"), p.name)
    return (10**6, p.name)


def version_label(version_name: str) -> str:
    suffix = version_name.removeprefix("version_")
    if len(suffix) == 1 and suffix.isalpha():
        return f"Version {suffix.upper()}"
    return version_name.replace("_", " ").title()


def version_key_for_winner(winner):
    if not winner:
        return None
    winner = str(winner).strip()
    if len(winner) == 1 and winner.isalpha():
        return f"version_{winner.lower()}"
    if winner.startswith("version_"):
        return winner
    return None


def version_dirs_for_scenario(scenario_dir: Path, mapping: dict) -> list[Path]:
    names: list[str] = []
    if isinstance(mapping, dict):
        names.extend(name for name in mapping if name.startswith("version_"))
    names.extend(
        d.name for d in sorted(scenario_dir.glob("version_*"), key=version_sort_key)
        if d.is_dir()
    )
    deduped = list(dict.fromkeys(names))
    return [scenario_dir / name for name in deduped if (scenario_dir / name).is_dir()]


def run_dirs_for_version(version_dir: Path) -> list[Path]:
    explicit_runs = sorted(
        (
            d for d in version_dir.glob("run-*")
            if d.is_dir() and (d / "outputs").is_dir()
        ),
        key=run_sort_key,
    )
    if explicit_runs:
        return explicit_runs
    if (version_dir / "outputs").is_dir():
        return [version_dir]
    return []


def build_run_block(run_dir: Path, run_label: str) -> str:
    outputs_dir = run_dir / "outputs"
    files_html = ""
    if outputs_dir.is_dir():
        files = sorted(f for f in outputs_dir.iterdir() if f.is_file())
        for f in files:
            if not is_office_preview_file(f, files):
                files_html += render_output_file(f)
    grading = load_json(run_dir / "grading.json")
    grading_html = ""
    if grading:
        rows = "".join(
            f'<li class="{"pass" if e["passed"] else "fail"}">{"✓" if e["passed"] else "✗"} {escape(e["text"])}'
            f'<div class="evidence">{escape(e.get("evidence",""))}</div></li>'
            for e in grading.get("expectations", [])
        )
        s = grading.get("summary", {})
        grading_html = (f'<div class="grading"><div class="grading-summary">{s.get("passed",0)}/{s.get("total",0)} '
                         f'expectations passed</div><ul class="expectations">{rows}</ul></div>')
    return f'<div class="run-block"><div class="run-label">{escape(run_label)}</div>{files_html}{grading_html}</div>'


def build_column(version_dir: Path, label: str) -> str:
    run_dirs = run_dirs_for_version(version_dir)
    if not run_dirs:
        body = '<div class="unsupported-note">No outputs found for this version.</div>'
    elif len(run_dirs) == 1:
        body = build_run_block(run_dirs[0], "Run 1")
    else:
        body = "".join(build_run_block(run_dir, run_dir.name.replace("-", " ").title()) for run_dir in run_dirs)
    run_count = len(run_dirs)
    run_note = f'<span class="run-count">{run_count} run{"s" if run_count != 1 else ""}</span>' if run_count else ""
    return f'<div class="column"><div class="column-label">{label}{run_note}</div>{body}</div>'


def build_scenario_section(workspace: Path, scenario_dir: Path, label_map: dict) -> str:
    sid = scenario_dir.name
    meta = load_json(scenario_dir / "eval_metadata.json", {})
    prompt = meta.get("prompt", "(no prompt found)")
    eval_name = meta.get("eval_name", sid)
    comparison = load_json(scenario_dir / "comparison.json")

    mapping = label_map.get(sid, {})  # e.g. {"version_a": "pdf_skill", "version_b": "doc_skill"}
    version_dirs = version_dirs_for_scenario(scenario_dir, mapping)

    columns = "".join(build_column(version_dir, version_label(version_dir.name)) for version_dir in version_dirs)
    if not columns:
        columns = '<div class="unsupported-note">No version directories found for this scenario.</div>'

    reveal_html = ""
    if mapping:
        reveal_text = "  |  ".join(
            f"{version_label(version_name)} = {config}"
            for version_name, config in sorted(mapping.items())
            if version_name.startswith("version_")
        )
        reveal_html = (
            f'<div class="reveal" data-labels="{escape_attr(reveal_text)}">'
            f'<button class="reveal-btn" onclick="revealLabels(this)">Reveal configurations</button>'
            f'<span class="reveal-result" style="display:none"></span></div>'
        )

    verdict_html = ""
    if comparison:
        winner = comparison.get("winner", "?")
        winner_label = version_label(version_key_for_winner(winner) or str(winner))
        reasoning = comparison.get("reasoning", "")
        oq = comparison.get("output_quality", {})
        score_bits = []
        for version_dir in version_dirs:
            label = version_label(version_dir.name)
            letter = label.removeprefix("Version ")
            score = oq.get(letter, {}).get("score", "—")
            score_bits.append(f"{label}: {score}/10")
        score_text = ", ".join(score_bits)
        verdict_html = (
            f'<details class="verdict"><summary>Blind judge verdict: {escape(winner_label)}'
            f' ({escape(score_text)})</summary>'
            f'<p class="reasoning">{escape(reasoning)}</p></details>'
        )

    return f'''
    <section class="scenario">
      <h2>{escape(eval_name)}</h2>
      <div class="prompt-block"><strong>Prompt:</strong> {escape(prompt)}</div>
      <div class="columns">{columns}</div>
      {verdict_html}
      {reveal_html}
    </section>
    '''


def build_summary_card(skill_name: str, scenario_dirs: list, label_map: dict, context: dict) -> str:
    total = len(scenario_dirs)
    wins_by_config: dict[str, int] = {}
    scored = 0
    for sd in scenario_dirs:
        comparison = load_json(sd / "comparison.json")
        mapping = label_map.get(sd.name, {})
        if comparison and mapping:
            winner_key = version_key_for_winner(comparison.get("winner"))
            winner_config = mapping.get(winner_key) if winner_key else None
            if winner_config:
                scored += 1
                wins_by_config[winner_config] = wins_by_config.get(winner_config, 0) + 1
    verdict = "No comparison data yet"
    if scored:
        leader, leader_wins = sorted(wins_by_config.items(), key=lambda item: (-item[1], item[0]))[0]
        if "with_skill" in wins_by_config:
            wins_with_skill = wins_by_config.get("with_skill", 0)
            pct = wins_with_skill / scored
            if pct >= 0.6:
                verdict = f"The skill helped in {wins_with_skill}/{scored} scenarios"
            elif pct <= 0.4:
                verdict = f"The skill did NOT clearly help -- won only {wins_with_skill}/{scored} scenarios"
            else:
                verdict = f"Mixed result -- the skill won {wins_with_skill}/{scored} scenarios"
        else:
            win_text = ", ".join(f"{config}: {wins}" for config, wins in sorted(wins_by_config.items()))
            verdict = f"Top configuration: {leader} ({leader_wins}/{scored} wins). Wins: {win_text}"
    chips = [
        ("Blind level", context.get("blind_level", "unknown")),
        ("Sampling", context.get("sampling_mode", "unknown")),
        ("Runs/config", str(context.get("runs_per_configuration", "unknown"))),
        ("Isolation", context.get("isolation_mode", "unknown")),
        ("Baseline contamination", context.get("baseline_contamination_risk", "unknown")),
        ("Side effects", context.get("side_effect_risk", "unknown")),
        ("Leakage risk", context.get("artifact_leakage_risk", "unknown")),
        ("Visual comparability", context.get("visual_comparability", "unknown")),
    ]
    chip_html = "".join(f'<span class="chip"><strong>{escape(k)}:</strong> {escape(v)}</span>' for k, v in chips)
    limitations = context.get("limitations", [])
    limitations_html = ""
    if limitations:
        limitations_html = '<ul class="limitations">' + ''.join(f'<li>{escape(str(item))}</li>' for item in limitations) + '</ul>'
    return f'''
    <div class="summary-card">
      <h1>eval-skills report: {escape(skill_name)}</h1>
      <div class="verdict-line">{escape(verdict)}</div>
      <div class="scenario-count">{total} scenario(s) tested</div>
      <div class="evidence-chips">{chip_html}</div>
      {limitations_html}
    </div>
    '''


CSS = '''
body { font-family: -apple-system, "Segoe UI", sans-serif; background: #f6f7f9; color: #1a1a1a; margin: 0; padding: 2rem; }
.summary-card { background: #fff; border-radius: 12px; padding: 1.5rem 2rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.summary-card h1 { margin: 0 0 0.5rem; font-size: 1.4rem; }
.verdict-line { font-size: 1.1rem; font-weight: 600; color: #1b5e20; }
.scenario-count { color: #666; font-size: 0.9rem; margin-top: 0.25rem; }
.evidence-chips { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 1rem; }
.chip { background: #eef2f7; border: 1px solid #d9e1ec; border-radius: 999px; padding: 0.3rem 0.65rem; font-size: 0.78rem; color: #3a4656; }
.limitations { margin: 0.75rem 0 0; color: #6b4f00; font-size: 0.86rem; }
.scenario { background: #fff; border-radius: 12px; padding: 1.5rem 2rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.scenario h2 { margin-top: 0; font-size: 1.15rem; }
.prompt-block { background: #f0f2f5; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.92rem; }
.columns { display: flex; gap: 1.5rem; align-items: flex-start; overflow-x: auto; }
.column { flex: 1 0 22rem; min-width: 0; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; }
.column-label { font-weight: 700; color: #555; margin-bottom: 0.75rem; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.04em; }
.run-count { float: right; color: #888; font-weight: 600; letter-spacing: 0; text-transform: none; }
.file-block { margin-bottom: 1rem; }
.file-name { font-size: 0.8rem; color: #888; margin-bottom: 0.35rem; }
.pdf-embed { width: 100%; height: 500px; border: 1px solid #ddd; border-radius: 4px; }
.html-embed { width: 100%; min-height: 420px; border: 1px solid #ddd; border-radius: 4px; background: #fff; }
.img-embed { max-width: 100%; border-radius: 4px; border: 1px solid #ddd; }
.text-embed { background: #fafafa; padding: 0.75rem; border-radius: 6px; font-size: 0.82rem; overflow-x: auto; white-space: pre-wrap; }
.unsupported-note { background: #fff4e5; color: #6b4f00; border: 1px solid #f3d19c; border-radius: 6px; padding: 0.65rem; font-size: 0.82rem; margin-bottom: 0.75rem; }
.download-link { margin-top: 0.5rem; font-size: 0.85rem; }
.run-block { border-top: 1px solid #eee; padding-top: 0.75rem; margin-top: 0.75rem; }
.run-block:first-of-type { border-top: 0; padding-top: 0; margin-top: 0; }
.run-label { color: #666; font-weight: 600; font-size: 0.78rem; margin-bottom: 0.5rem; }
.grading { margin-top: 0.75rem; border-top: 1px solid #eee; padding-top: 0.75rem; }
.grading-summary { font-weight: 600; font-size: 0.85rem; margin-bottom: 0.4rem; }
.expectations { list-style: none; padding: 0; margin: 0; font-size: 0.82rem; }
.expectations li { padding: 0.3rem 0; border-bottom: 1px dashed #eee; }
.expectations li.pass { color: #1b5e20; }
.expectations li.fail { color: #b71c1c; }
.evidence { color: #777; font-size: 0.78rem; margin-left: 1.1rem; }
.verdict { margin-top: 1rem; background: #fffbe6; border-radius: 8px; padding: 0.6rem 1rem; font-size: 0.88rem; }
.verdict summary { cursor: pointer; font-weight: 600; }
.reasoning { margin: 0.5rem 0 0; color: #444; }
.reveal { margin-top: 0.75rem; }
.reveal-btn { background: #1a1a1a; color: #fff; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
.reveal-result { margin-left: 0.75rem; font-weight: 600; }
'''

JS = '''
function revealLabels(btn) {
  const wrap = btn.parentElement;
  const labels = wrap.getAttribute("data-labels");
  const result = wrap.querySelector(".reveal-result");
  result.textContent = labels;
  result.style.display = "inline";
  btn.disabled = true;
}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--skill-name", default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    workspace = args.workspace.resolve()
    skill_name = args.skill_name or workspace.name
    label_map = load_json(workspace / "label_key.json", {})
    context = load_json(workspace / "evaluation_context.json", {})

    scenario_dirs = sorted(
        d for d in workspace.iterdir() if d.is_dir() and d.name.startswith("scenario-")
    )

    sections = "".join(build_scenario_section(workspace, sd, label_map) for sd in scenario_dirs)
    summary = build_summary_card(skill_name, scenario_dirs, label_map, context)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>eval-skills report: {escape(skill_name)}</title>
<style>{CSS}</style>
</head>
<body>
{summary}
{sections}
<script>{JS}</script>
</body>
</html>'''

    out_path = args.out or (workspace / "comparison_report.html")
    out_path.write_text(html)
    print(f"Wrote comparison report to {out_path}")


if __name__ == "__main__":
    main()
