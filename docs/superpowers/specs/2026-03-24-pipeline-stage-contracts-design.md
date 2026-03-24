# Pipeline Stage Contracts and Engine Design

日期：2026-03-24  
范围：AutoPatent Pipeline 执行基础设施

## 1. 目标

在 AutoPatent 的阶段化执行模型里，通过合同/引擎的基础设施保证：

1. 阶段（Stage）可以声明自己的输入依赖与产出（`requires`/`produces`）并返回结构化结果。
2. 引擎按照声明的顺序执行阶段，确保交付链的可追踪性，方便后续添加依赖检查或重试。
3. 执行上下文能承载工作目录（`work_dir`）与随需扩展的元数据。

## 2. 关键约束

1. 目前仅需满足顺序执行，后续再添加依赖/SLA 逻辑即可。
2. 兼容 Python 3.9，因此在类型提示上避免 PEP 604。
3. 所有定义都暴露在 `autopatent.pipeline` 包下，方便后续扩展。

## 3. 设计

### 3.1 阶段合同（contracts.py）

- `StageContext`: dataclass 包含必需的 `work_dir: Path` 和可扩展的 `metadata`（`dict[str, Any]`）。
- `StageResult`: dataclass 包含 `produces: list[str]`，阶段可以在运行后报告产出标识。
- `Stage` Protocol 明确：
  - `stage_id`: 阶段唯一标识
  - `requires`, `produces`: 入参/出参签名
  - `run(ctx: StageContext) -> StageResult`

### 3.2 引擎（engine.py）

- `PipelineEngine` 接受任意可迭代的 `Stage`，在初始化时记录一份列表。
- `run(context: StageContext)` 按顺序依次调用 `stage.run(context)` 并忽略返回值（现阶段只关心执行顺序）。
- 实现尽量简单，为未来加 checkpoint、并发、依赖检查留出钩子。

### 3.3 包暴露

- `autopatent.pipeline.__init__` 将上述合同与引擎导出，供上层 CLI/服务直接使用。

### 3.4 测试

- 新增烟雾测试 `tests/test_pipeline_smoke.py`，通过 stub 阶段记录 `run` 调用顺序，确保 `PipelineEngine.run` 以 `stages` 提供的顺序执行。

## 4. 校验与下一步

1. 本阶段围绕顺序执行与最小合同展开，暂不涉及 checkpoint、错误策略或阶段并行。
2. 未来可以扩展 `StageContext` 为阶段共享的 artifact 仓库、让 `StageResult` 包含状态与日志、并在 `PipelineEngine` 中参与依赖验证/失败恢复。
