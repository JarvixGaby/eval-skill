# eval-skills

[English README](./README.md)

`eval-skills` 是一个用于评估 Agent Skill 是否真的有用的 Skill。它会把一个或多个目标 Skill 变成小型基准测试：生成真实场景、运行 baseline 或 skill-vs-skill 配置、给结果打分、聚合指标，并生成一份并排对比的 HTML 报告。

它要回答的问题不是“这个 Skill 自己说得好不好”，而是：

```text
和直接让 Agent 做相比，这个 Skill 是否真的改善了结果？或者两个候选 Skill 谁更好？
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

让 Agent 使用 `eval-skills`，并提供你想评估的目标 Skill 来源；也可以一次提供多个候选 Skill 来源。

示例：

```text
Use eval-skills to evaluate https://github.com/example/example-skill.
```

两个 Skill 互测示例：

```text
Use eval-skills to compare /path/to/skill-one and /path/to/skill-two.
Do not include a naked baseline.
```

你可以提供以下任意一种目标来源：

- GitHub 仓库 URL。
- 本地 Skill 目录。
- `.skill` 压缩包。
- 一条安装命令。
- 粘贴的 `SKILL.md` 内容，以及它引用的文件。
- 已注册 Skill 的名称。

如果你要求评估但没有提供任何 Skill source，Agent 应该先提醒你提供上面任意一种来源，然后再开始生成场景或创建 workspace。

如果你只提供了一个目标，Agent 默认与裸模型 baseline 对比。你也可以明确要求：

- 裸模型 baseline，也就是不使用任何 Skill。
- 另一个已注册 Skill，用已安装的 skill name 指定。
- 另一个未注册 Skill 来源，例如 GitHub URL、本地目录、`.skill` 压缩包、安装命令或粘贴文件。

如果你已经提供了两个或更多 Skill 来源，或者明确说不要加入裸模型 baseline，Agent 应该直接进入 skill-vs-skill 对比。

用户通常只需要提供：

- 目标 Skill 的来源，或多个候选 Skill 的来源。
- 哪些能力想测，或者哪些内容不要测。
- 如果目标 Skill 依赖真实输入文件，可以提供这些文件。
- 是否允许外部副作用。默认不允许。

之后 `eval-skills` 会：

1. 把目标 Skill 克隆或复制到 `temp/target-skill/`；多个候选 Skill 放到 `temp/target-skills/<configuration-name>/`。
2. 阅读目标 Skill 或候选 Skill，分析能力范围。
3. 根据目标 Skill 的真实用途，或多个候选 Skill 的共同能力范围生成测试场景。
4. 对每个场景运行所有 configuration。
5. 对每次 run 打分。
6. 使用统一的 N-way rubric 对所有匿名版本做盲对比。
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

- 每个 configuration：3 次。

如果是 baseline 对比，configuration 通常是 `with_skill` 和 `without_skill`。如果是两个 Skill 互测且不加入裸模型 baseline，可以使用 `skill_one`、`skill_two` 这样的名称。HTML 报告必须展示每个 blinded version 的 3 次 run。不能只展示最好的一次、第一次，或者用平均摘要替代真实输出。

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
│   ├── target-skills/
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

- **baseline 或 skill-vs-skill 对比**：不是只看目标 Skill 自己的声明，而是和裸模型 baseline 或其他候选 Skill 比较。
- **自动生成真实场景**：测试 prompt 来自目标 Skill 的 description、workflow 和常见用途。
- **隔离目标 Skill**：默认把目标 Skill 当作本地 artifact，不安装到全局，降低配置之间互相污染的风险。
- **固定 3 次 run**：每个配置重复 3 次，让失败和波动可见。
- **工作区校验**：`validate_workspace.py` 会在报告前检查目录、JSON、run 数量和输出是否齐全。
- **并排 HTML 报告**：把 A/B 输出嵌入同一个静态 HTML，方便直接比较。
- **诚实标注证据强度**：报告会记录 blind level、side-effect risk、leakage risk 和 limitations。
- **目录干净**：所有工作文件进入 `temp/`，最终报告留在 workspace 根目录。
- **不可信目标防护**：默认不执行目标 Skill 的安装器或脚本，并转义目标控制的 HTML 内容。

## 原理介绍

`eval-skills` 把一个 Skill 当作黑盒产品来评估。

1. **获取并隔离目标 Skill**  
   目标 Skill 会被克隆或复制到 `temp/target-skill/`；多个候选 Skill 可以放到 `temp/target-skills/<configuration-name>/`。默认不安装到全局 skills 目录，因为全局安装可能污染对比。

2. **分析目标 Skill**  
   `scripts/analyze_skill.py` 会读取 `SKILL.md` 和 bundled resources，生成第一版 `skill_profile.json`。Agent 仍然需要自己阅读目标 Skill，并在必要时修正这个 profile。

3. **生成测试场景**  
   Agent 根据目标 Skill 声称的能力和真实用法生成场景；如果是多个候选 Skill，则基于它们共同覆盖的能力范围生成场景。prompt 本身应该能自然触发 intended trigger surface，因此默认不单独做 trigger test。

4. **运行所有 configuration**  
   每个场景会随机分配 Version A 和 Version B。baseline 对比时，一个版本拿到 Skill path，另一个版本只拿到任务 prompt 和 fixtures；两个 Skill 互测时，每个版本只拿到自己对应的 Skill path。

5. **清洗与打分**  
   用户可见的最终输出进入 `outputs/`，过程痕迹保留在 `raw_outputs/`。每次 run 都会按场景 expectations 打分。

6. **盲对比与揭盲分析**  
   comparator 先只看 blinded versions 的清洗后输出，不看身份。对比完成后再揭盲，分析哪个 configuration 更好以及原因。

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
