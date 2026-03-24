# AutoPatent CN MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 AutoPatent 的中国发明专利 MVP CLI，实现从输入摄入到专利草案包导出的 16 阶段流水线，并支持方向关卡、模板默认回退、检索证据与 `--resume`。

**Architecture:** 采用“配置 + 阶段契约 + 可恢复执行器”结构。CLI 只负责参数和运行控制，阶段实现通过统一 `StageContext` 读写工件。模板系统使用统一 `disclosure_context.json`，渲染 Markdown 和 DOCX。检索模块先做可插拔资源层和标准化证据记录。

**Tech Stack:** Python 3.11、Typer（CLI）、Pydantic（配置/模型）、Jinja2（模板渲染）、python-docx（DOCX 生成）、pytest（测试）

---

## File Structure

### Core Package
- Create: `autopatent/__init__.py`
- Create: `autopatent/cli.py`
- Create: `autopatent/config.py`
- Create: `autopatent/models.py`
- Create: `autopatent/logging.py`

### Pipeline
- Create: `autopatent/pipeline/__init__.py`
- Create: `autopatent/pipeline/contracts.py`
- Create: `autopatent/pipeline/engine.py`
- Create: `autopatent/pipeline/checkpoint.py`
- Create: `autopatent/pipeline/stages/stage_00_input_ingest.py`
- Create: `autopatent/pipeline/stages/stage_01_direction_discovery.py`
- Create: `autopatent/pipeline/stages/stage_02_prior_art_scan.py`
- Create: `autopatent/pipeline/stages/stage_03_direction_scoring.py`
- Create: `autopatent/pipeline/stages/stage_04_human_direction_gate.py`
- Create: `autopatent/pipeline/stages/stage_05_to_15_stubs.py`

### Search and Evidence
- Create: `autopatent/search/__init__.py`
- Create: `autopatent/search/resources.py`
- Create: `autopatent/search/query_builder.py`
- Create: `autopatent/search/dedup.py`
- Create: `autopatent/search/evidence_summary.py`

### Template System
- Create: `autopatent/templates/__init__.py`
- Create: `autopatent/templates/renderer.py`
- Create: `autopatent/templates/defaults/cn_invention_default.md.j2`
- Create: `autopatent/templates/defaults/cn_invention_default.docx.j2.md`

### Tests
- Create: `tests/test_cli_run_modes.py`
- Create: `tests/test_checkpoint_resume.py`
- Create: `tests/test_direction_gate.py`
- Create: `tests/test_template_default_fallback.py`
- Create: `tests/test_disclosure_render.py`
- Create: `tests/test_prior_art_resources.py`
- Create: `tests/test_pipeline_smoke.py`

### Packaging and Docs
- Create: `pyproject.toml`
- Create: `.gitignore`
- Modify: `README.md`

## Task 1: 项目骨架与 CLI 入口

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `autopatent/__init__.py`
- Create: `autopatent/cli.py`
- Test: `tests/test_cli_run_modes.py`

- [ ] **Step 1: 写 CLI 参数解析失败测试**

```python
def test_run_requires_topic_or_input_doc(runner):
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0
    assert "需要至少一个输入" in result.stdout
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_cli_run_modes.py::test_run_requires_topic_or_input_doc -v`  
Expected: FAIL（`app`/命令未实现）

- [ ] **Step 3: 最小实现 CLI 与命令骨架**

```python
@app.command()
def run(topic: str | None = None, input_doc: Path | None = None):
    if not topic and not input_doc:
        raise typer.BadParameter("需要至少一个输入")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_cli_run_modes.py -v`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml .gitignore autopatent/__init__.py autopatent/cli.py tests/test_cli_run_modes.py
git commit -m "feat: bootstrap AutoPatent package and CLI run command"
```

## Task 2: 配置模型与检查点机制

**Files:**
- Create: `autopatent/config.py`
- Create: `autopatent/models.py`
- Create: `autopatent/pipeline/checkpoint.py`
- Test: `tests/test_checkpoint_resume.py`

- [ ] **Step 1: 写检查点读写失败测试**

```python
def test_resume_reads_latest_stage(tmp_path):
    ckpt = CheckpointStore(tmp_path / "state")
    ckpt.save(stage_id="STAGE_04", status="done")
    assert ckpt.latest().stage_id == "STAGE_04"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_checkpoint_resume.py::test_resume_reads_latest_stage -v`  
Expected: FAIL（类不存在）

- [ ] **Step 3: 实现配置加载 + checkpoint 存储**

```python
class CheckpointStore:
    def save(self, stage_id: str, status: str) -> None: ...
    def latest(self) -> Checkpoint | None: ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_checkpoint_resume.py -v`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/config.py autopatent/models.py autopatent/pipeline/checkpoint.py tests/test_checkpoint_resume.py
git commit -m "feat: add config schema and checkpoint resume storage"
```

## Task 3: Pipeline 引擎与阶段契约

**Files:**
- Create: `autopatent/pipeline/contracts.py`
- Create: `autopatent/pipeline/engine.py`
- Create: `autopatent/pipeline/__init__.py`
- Test: `tests/test_pipeline_smoke.py`

- [ ] **Step 1: 写最小流水线顺序执行测试**

```python
def test_engine_runs_stages_in_order(tmp_path):
    order = []
    engine = PipelineEngine(stages=[stub("A", order), stub("B", order)])
    engine.run(context=ctx(tmp_path))
    assert order == ["A", "B"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_pipeline_smoke.py::test_engine_runs_stages_in_order -v`  
Expected: FAIL

- [ ] **Step 3: 实现 StageContract 与 Engine**

```python
class Stage(Protocol):
    stage_id: str
    requires: list[str]
    produces: list[str]
    def run(self, ctx: StageContext) -> StageResult: ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_pipeline_smoke.py -v`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/pipeline/contracts.py autopatent/pipeline/engine.py autopatent/pipeline/__init__.py tests/test_pipeline_smoke.py
git commit -m "feat: implement pipeline stage contracts and engine"
```

## Task 4: Stage 00-04（方向分析与人工关卡）

**Files:**
- Create: `autopatent/pipeline/stages/stage_00_input_ingest.py`
- Create: `autopatent/pipeline/stages/stage_01_direction_discovery.py`
- Create: `autopatent/pipeline/stages/stage_02_prior_art_scan.py`
- Create: `autopatent/pipeline/stages/stage_03_direction_scoring.py`
- Create: `autopatent/pipeline/stages/stage_04_human_direction_gate.py`
- Test: `tests/test_direction_gate.py`
- Test: `tests/test_prior_art_resources.py`

- [ ] **Step 1: 写方向关卡命令行为测试**

```python
def test_human_gate_choose_persists_decision(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "choose 2")
    stage = HumanDirectionGateStage()
    result = stage.run(ctx_with_candidates(tmp_path))
    assert result.outputs["selected_direction_id"] == "2"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_direction_gate.py::test_human_gate_choose_persists_decision -v`  
Expected: FAIL

- [ ] **Step 3: 实现 Stage 00-04 最小可运行版本**

```python
# Stage 04 支持命令: choose / expand / merge / drop / quit
# 弱质量候选触发 expand，最多 3 次
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_direction_gate.py tests/test_prior_art_resources.py -v`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/pipeline/stages/stage_00_input_ingest.py autopatent/pipeline/stages/stage_01_direction_discovery.py autopatent/pipeline/stages/stage_02_prior_art_scan.py autopatent/pipeline/stages/stage_03_direction_scoring.py autopatent/pipeline/stages/stage_04_human_direction_gate.py tests/test_direction_gate.py tests/test_prior_art_resources.py
git commit -m "feat: add direction discovery, prior-art scan, scoring and human gate stages"
```

## Task 5: 模板系统与“未指定模板默认内置模板”规则

**Files:**
- Create: `autopatent/templates/renderer.py`
- Create: `autopatent/templates/defaults/cn_invention_default.md.j2`
- Create: `autopatent/templates/defaults/cn_invention_default.docx.j2.md`
- Test: `tests/test_template_default_fallback.py`
- Test: `tests/test_disclosure_render.py`

- [ ] **Step 1: 写模板默认回退测试**

```python
def test_default_template_used_when_not_specified(tmp_path):
    cfg = load_cfg_without_template(tmp_path)
    out = render_disclosure(cfg, context=sample_context())
    assert "cn_invention_default" in out.template_name
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_template_default_fallback.py::test_default_template_used_when_not_specified -v`  
Expected: FAIL

- [ ] **Step 3: 实现 renderer 与默认模板逻辑**

```python
template_name = user_template or "cn_invention_default"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_template_default_fallback.py tests/test_disclosure_render.py -v`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/templates/renderer.py autopatent/templates/defaults/cn_invention_default.md.j2 autopatent/templates/defaults/cn_invention_default.docx.j2.md tests/test_template_default_fallback.py tests/test_disclosure_render.py
git commit -m "feat: implement disclosure template rendering with built-in default fallback"
```

## Task 6: Stage 06-15 产物链路与导出包

**Files:**
- Create: `autopatent/pipeline/stages/stage_05_to_15_stubs.py`
- Modify: `autopatent/pipeline/engine.py`
- Test: `tests/test_pipeline_smoke.py`

- [ ] **Step 1: 写端到端产物存在性测试**

```python
def test_mvp_outputs_key_artifacts(tmp_path):
    run_pipeline(tmp_path)
    assert (tmp_path / "deliverables/disclosure.md").exists()
    assert (tmp_path / "deliverables/oa_response_playbook.md").exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_pipeline_smoke.py::test_mvp_outputs_key_artifacts -v`  
Expected: FAIL

- [ ] **Step 3: 实现 Stage 05-15 的最小产物写出**

```python
# 先用 MVP stub 输出稳定工件，后续再逐步增强内容质量
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_pipeline_smoke.py -v`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/pipeline/stages/stage_05_to_15_stubs.py autopatent/pipeline/engine.py tests/test_pipeline_smoke.py
git commit -m "feat: add stage 05-15 mvp artifact pipeline and deliverable export"
```

## Task 7: README 与运行文档收口

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-03-24-autopatent-cn-mvp-design.md`

- [ ] **Step 1: 写 README 命令示例**

```bash
python -m autopatent.cli run --topic "示例主题" --output ./artifacts/demo
python -m autopatent.cli run --input-doc ./seed.md --code-dir ./impl --resume
```

- [ ] **Step 2: 补充模板默认行为与交互命令说明**

Expected: README 明确写出  
`--template` 未指定时默认 `cn_invention_default`

- [ ] **Step 3: 运行全量测试**

Run: `pytest -v`  
Expected: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add README.md docs/superpowers/specs/2026-03-24-autopatent-cn-mvp-design.md
git commit -m "docs: add usage guide and confirm default template behavior"
```

## Final Verification Checklist

- [ ] `pytest -v` 全量通过
- [ ] `python -m autopatent.cli run --help` 可用
- [ ] `--resume` 能正确从 checkpoint 继续
- [ ] Stage 04 交互命令 `choose/expand/merge/drop/quit` 行为符合 spec
- [ ] 未指定模板时，默认走 `cn_invention_default`

