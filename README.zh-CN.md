# eval-skills

[English README](./README.md)

`eval-skills` 是一个用于评估其他 Agent Skill 是否真的有用的 Skill。它会把目标 Skill 变成一个小型基准测试：生成真实场景、分别运行“使用 Skill”和“不使用 Skill”的版本、给结果打分、聚合指标，并生成一份并排对比的 HTML 报告。

它要回答的问题不是“这个 Skill 自己说得好不好”，而是：

```text
和直接让 Agent 做相比，这个 Skill 是否真的改善了结果？
```

## 安装方式

### 让 Agent 帮你安装

把下面这段发给有 shell 权限的 Agent：

```text
请帮我安装 eval-skills：
https://github.com/JarvixGaby/eval-skill

请把它克隆到我的 Agent skills 目录，目录名为 eval-skills。
安装后请确认 SKILL.md、README.md、agents/、references/、scripts/ 都存在。
```

如果使用 Codex 风格的本地 skills，通常安装到：

```bash
~/.codex/skills/eval-skills
```

如果使用 Claude 风格的本地 skills，通常安装到：

```bash
~/.claude/skills/eval-skills
```

### 手动安装

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/JarvixGaby/eval-skill ~/.codex/skills/eval-skills
```

如果你使用的是其他 Agent，把这个仓库放到对应的 skills 目录即可。仓库根目录需要包含 `SKILL.md`。

## Skill 使用方法

让 Agent 使用 `eval-skills`，并提供你想评估的目标 Skill 来源。

示例：

```text
Use eval-skills to evaluate https://github.com/example/example-skill.
```

你可以提供以下任意一种目标来源：

- GitHub 仓库 URL。
- 本地 Skill 目录。
- `.skill` 压缩包。
- 一条安装命令。
- 粘贴的 `SKILL.md` 内容，以及它引用的文件。

用户通常只需要提供：

- 目标 Skill 的来源。
- 哪些能力想测，或者哪些内容不要测。
- 如果目标 Skill 依赖真实输入文件，可以提供这些文件。
- 是否允许外部副作用。默认不允许。

之后 `eval-skills` 会：

1. 把目标 Skill 克隆或复制到 `temp/target-skill/`。
2. 阅读目标 Skill，分析能力范围。
3. 根据目标 Skill 的真实用途生成测试场景。
4. 对每个场景分别运行 with-skill 和 baseline。
5. 对每次 run 打分。
6. 对 Version A 和 Version B 做盲对比。
7. 聚合结果。
8. 生成 `comparison_report.html`。

## 标准评估模式

`eval-skills` 只保留一种标准模式：

```json
{
  "sampling_mode": "standard",
  "runs_per_configuration": 3
}
```

每个场景都会运行：

- 使用目标 Skill：3 次。
- 不使用目标 Skill：3 次。

HTML 报告必须展示 Version A 的 3 次 run 和 Version B 的 3 次 run。不能只展示最好的一次、第一次，或者用平均摘要替代真实输出。

## 目录结构

发布到 GitHub 时，仓库应包含：

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

一次正常评估会在用户 workspace 中生成：

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

## 核心优势

- **先和 baseline 对比**：不是只看目标 Skill 自己的声明，而是和“直接让 Agent 做”比较。
- **自动生成真实场景**：测试 prompt 来自目标 Skill 的 description、workflow 和常见用途。
- **隔离目标 Skill**：默认把目标 Skill 当作本地 artifact，不安装到全局，降低 baseline 污染风险。
- **固定 3 次 run**：每个配置重复 3 次，让失败和波动可见。
- **工作区校验**：`validate_workspace.py` 会在报告前检查目录、JSON、run 数量和输出是否齐全。
- **并排 HTML 报告**：把 A/B 输出嵌入同一个静态 HTML，方便直接比较。
- **诚实标注证据强度**：报告会记录 blind level、side-effect risk、leakage risk 和 limitations。
- **目录干净**：所有工作文件进入 `temp/`，最终报告留在 workspace 根目录。

## 原理介绍

`eval-skills` 把一个 Skill 当作黑盒产品来评估。

1. **获取并隔离目标 Skill**  
   目标 Skill 会被克隆或复制到 `temp/target-skill/`。默认不安装到全局 skills 目录，因为全局安装可能污染 baseline。

2. **分析目标 Skill**  
   `scripts/analyze_skill.py` 会读取 `SKILL.md` 和 bundled resources，生成第一版 `skill_profile.json`。Agent 仍然需要自己阅读目标 Skill，并在必要时修正这个 profile。

3. **生成测试场景**  
   Agent 根据目标 Skill 声称的能力和真实用法生成场景。prompt 本身应该能自然触发目标 Skill 的 intended trigger surface，因此默认不单独做 trigger test。

4. **分别运行 with-skill 和 baseline**  
   每个场景会随机分配 Version A 和 Version B。一个版本拿到 Skill path，另一个版本只拿到任务 prompt 和 fixtures。

5. **清洗与打分**  
   用户可见的最终输出进入 `outputs/`，过程痕迹保留在 `raw_outputs/`。每次 run 都会按场景 expectations 打分。

6. **盲对比与揭盲分析**  
   comparator 先只看 Version A/B 的清洗后输出，不看身份。对比完成后再揭盲，分析 Skill 为什么有帮助或没有帮助。

7. **校验、聚合、生成报告**  
   先校验 workspace，再聚合 benchmark，最后生成静态 `comparison_report.html`。

## 常用命令

分析目标 Skill：

```bash
python3 scripts/analyze_skill.py <workspace>/temp/target-skill \
  --out <workspace>/temp/skill_profile.json
```

校验 workspace：

```bash
python3 scripts/validate_workspace.py <workspace>/temp
```

聚合指标：

```bash
python3 scripts/aggregate_benchmark.py <workspace>/temp \
  --skill-name <skill-name>
```

生成 HTML 报告：

```bash
python3 scripts/generate_comparison_report.py <workspace>/temp \
  --skill-name <skill-name> \
  --out <workspace>/comparison_report.html
```

## 说明

- 默认避免外部副作用。如果目标 Skill 会发邮件、部署服务、写入 SaaS、购买、删除或改变真实状态，除非用户明确批准，否则使用 sandbox 或 dry-run 场景。
- 这个 Skill 产出的是证据，不是绝对结论。报告应清楚写明 blind level、limitations 和 residual risks。
- 最终报告是静态 HTML，可以本地打开，也可以作为 artifact 分享。
