# Sansec Disclosure Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增可通过 `--template sansec_disclosure_v1` 选择的 disclosure 模板，实现“技术交底书主体 + 检索报告附录”输出，且不影响默认模板与非 disclosure 产物。

**Architecture:** 复用现有 `render_disclosure()` 模板加载机制，仅新增 `defaults` 模板文件并补充最小上下文文本化字段（列表转文本）以避免模板循环语法。通过单元测试与 CLI 集成测试确保模板可渲染、结构正确、回退机制无回归。

**Tech Stack:** Python 3.11, 自研模板渲染器 (`autopatent/templates/renderer.py`), pytest, Typer CLI

---

## File Structure

- Create: `autopatent/templates/defaults/sansec_disclosure_v1.md.j2`
- Create: `autopatent/templates/defaults/sansec_disclosure_v1.docx.j2.md`
- Modify: `autopatent/pipeline/stages/stage_05_to_15_stubs.py`
- Modify: `tests/test_disclosure_render.py`
- Modify: `tests/test_cli_pipeline_execution.py`
- Modify: `README.md`

### Responsibilities

- `sansec_disclosure_v1.*`：承载新模板版式（主体 + 附录A 检索报告要点）
- `stage_05_to_15_stubs.py`：提供模板可直接使用的文本化字段（如 `evidence_refs_text`）
- `test_disclosure_render.py`：验证模板渲染成功、占位符完整替换
- `test_cli_pipeline_execution.py`：验证 CLI 使用新模板可端到端产出 disclosure
- `README.md`：补充模板启用方式与边界说明

---

### Task 1: 用测试锁定新模板行为（TDD）

**Files:**
- Modify: `tests/test_disclosure_render.py`
- Modify: `tests/test_cli_pipeline_execution.py`
- Test: `tests/test_disclosure_render.py`
- Test: `tests/test_cli_pipeline_execution.py`

- [ ] **Step 1: 在 `test_disclosure_render.py` 添加失败用例（新模板存在且可渲染）**

```python
def test_sansec_disclosure_template_renders_with_appendix():
    from autopatent.templates.renderer import render_disclosure

    context = {
        "title": "T",
        "technical_field": "F",
        "background": "B",
        "summary": "S",
        "embodiments": "E",
        "invention_title": "IT",
        "technical_field_cn": "TF",
        "background_art": "BA",
        "core_solution": "CS",
        "technical_effects": "TE",
        "embodiments_detail": "ED",
        "evidence_refs_text": "- e1\\n- e2",
        "claim_seed_points_text": "- c1\\n- c2",
        "code_evidence_text": "- code/a.c",
    }
    rendered = render_disclosure(context=context, template_name="sansec_disclosure_v1")
    assert "附录A 检索报告要点" in rendered.markdown
    assert "{{" not in rendered.markdown
```

- [ ] **Step 2: 运行单测并确认失败（模板尚未创建）**

Run: `PYTHONPATH=. pytest -q tests/test_disclosure_render.py::test_sansec_disclosure_template_renders_with_appendix`  
Expected: FAIL，报 `Template files not found for: sansec_disclosure_v1`

- [ ] **Step 3: 在 `test_cli_pipeline_execution.py` 添加失败用例（CLI + --template）**

```python
def test_run_uses_sansec_disclosure_template(tmp_path):
    runner = CliRunner()
    output_dir = tmp_path / "run-sansec-template"
    result = runner.invoke(
        app,
        ["run", "--topic", "抗量子SSL和证书", "--output", str(output_dir), "--auto-approve", "--template", "sansec_disclosure_v1"],
    )
    assert result.exit_code == 0
    disclosure = (output_dir / "artifacts" / "disclosure.md").read_text(encoding="utf-8")
    assert "附录A 检索报告要点" in disclosure
```

- [ ] **Step 4: 运行该测试并确认失败**

Run: `PYTHONPATH=. pytest -q tests/test_cli_pipeline_execution.py::test_run_uses_sansec_disclosure_template`  
Expected: FAIL，无法加载模板或断言未命中

- [ ] **Step 5: 提交测试基线（仅测试）**

```bash
git add tests/test_disclosure_render.py tests/test_cli_pipeline_execution.py
git commit -m "test(template): 增加 sansec_disclosure_v1 渲染与CLI用例" -m $'- 新增 disclosure 模板渲染失败用例\n- 新增 CLI 使用 --template 的端到端失败用例\n- 为后续模板实现提供 TDD 基线'
```

---

### Task 2: 实现 `sansec_disclosure_v1` 模板与上下文文本化字段

**Files:**
- Create: `autopatent/templates/defaults/sansec_disclosure_v1.md.j2`
- Create: `autopatent/templates/defaults/sansec_disclosure_v1.docx.j2.md`
- Modify: `autopatent/pipeline/stages/stage_05_to_15_stubs.py`
- Test: `tests/test_disclosure_render.py`
- Test: `tests/test_cli_pipeline_execution.py`

- [ ] **Step 1: 在 `stage_05_to_15_stubs.py` 添加列表字段文本化函数**

```python
def _list_to_text(items: Any, prefix: str = "- ") -> str:
    if not isinstance(items, list):
        return ""
    rows = [f"{prefix}{str(x)}" for x in items if str(x).strip()]
    return "\n".join(rows)
```

- [ ] **Step 2: 在 `_build_disclosure_context()` 注入文本化字段**

```python
"evidence_refs_text": _list_to_text([...]),
"claim_seed_points_text": _list_to_text([...]),
"code_evidence_text": _list_to_text([...]),
```

- [ ] **Step 3: 创建 `sansec_disclosure_v1.md.j2`（主体 + 附录A）**

```markdown
# {{ title }}
## 技术领域
{{ technical_field_cn }}
...
## 附录A 检索报告要点
### 检索依据
{{ evidence_refs_text }}
### 权利要求线索
{{ claim_seed_points_text }}
### 代码证据
{{ code_evidence_text }}
```

- [ ] **Step 4: 创建 `sansec_disclosure_v1.docx.j2.md`（与 md 模板一致结构）**

Run: 手工复制 `md.j2` 结构并调整 DOCX 友好标题层级  
Expected: `render_disclosure(...).docx_markdown` 可直接输出

- [ ] **Step 5: 运行新增测试验证通过**

Run:  
`PYTHONPATH=. pytest -q tests/test_disclosure_render.py::test_sansec_disclosure_template_renders_with_appendix`  
`PYTHONPATH=. pytest -q tests/test_cli_pipeline_execution.py::test_run_uses_sansec_disclosure_template`

Expected: PASS

- [ ] **Step 6: 提交模板实现**

```bash
git add autopatent/templates/defaults/sansec_disclosure_v1.md.j2 \
        autopatent/templates/defaults/sansec_disclosure_v1.docx.j2.md \
        autopatent/pipeline/stages/stage_05_to_15_stubs.py
git commit -m "feat(template): 新增 sansec_disclosure_v1 disclosure 模板" -m $'- 新增 sansec_disclosure_v1 两套模板文件\n- disclosure 模板采用技术交底书主体 + 检索报告附录结构\n- 增加 disclosure_context 列表字段文本化输出，避免模板循环语法依赖'
```

---

### Task 3: 文档更新与全量回归

**Files:**
- Modify: `README.md`
- Modify: `tests/test_disclosure_render.py` (如需补充断言)
- Modify: `tests/test_cli_pipeline_execution.py` (如需补充断言)
- Test: `tests/` 全量

- [ ] **Step 1: 更新 README 模板使用说明**

Add section:
- `--template sansec_disclosure_v1` 用法
- 适用范围仅 `disclosure`
- 源模板语义：技术交底书主体 + 检索报告附录

- [ ] **Step 2: 运行全量测试**

Run: `PYTHONPATH=. pytest -q`  
Expected: All PASS

- [ ] **Step 3: 执行一次本地 smoke 命令**

Run:
`PYTHONPATH=. python -m autopatent.cli run --topic "抗量子SSL和证书" --template sansec_disclosure_v1 --output /tmp/autopatent-sansec-smoke --auto-approve`

Expected:
- `/tmp/autopatent-sansec-smoke/artifacts/disclosure.md` 存在
- 文本含 `附录A 检索报告要点`

- [ ] **Step 4: 提交文档与收尾变更**

```bash
git add README.md tests/test_disclosure_render.py tests/test_cli_pipeline_execution.py
git commit -m "docs(template): 补充 sansec_disclosure_v1 使用说明与验收说明" -m $'- README 增加新模板启用方式\n- 明确新模板仅作用于 disclosure 输出\n- 补充模板相关测试断言与回归验证记录'
```

---

## Final Verification Checklist

- [ ] `render_disclosure(template_name="sansec_disclosure_v1")` 可渲染
- [ ] `artifacts/disclosure.md` 包含“附录A 检索报告要点”
- [ ] `deliverables/disclosure.md` 同步包含附录章节
- [ ] 默认模板 `cn_invention_default` 相关测试不回归
- [ ] 全量测试通过

---

## Execution Notes

1. 严格按 TDD 顺序执行（先测后改）
2. 每个 Task 独立提交，避免混合提交
3. 不要提前实现子项目 2（搜索扩展）

