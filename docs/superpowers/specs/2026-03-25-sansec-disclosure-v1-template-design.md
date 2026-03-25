# Sansec Disclosure 模板设计（子项目 1）

## 1. 背景与目标

当前 AutoPatent 仅内置 `cn_invention_default` 模板，用户希望复用 `SansecPatentTempl` 中的已有文档格式，并通过现有 `--template` 机制切换模板，而不是将模板硬编码到流水线中。

本设计仅覆盖模板子项目，目标是新增一个可配置模板 `sansec_disclosure_v1`，用于 `STAGE_07 disclosure` 渲染。

## 2. 范围与非目标

### 2.1 范围（In Scope）

1. 新增模板名：`sansec_disclosure_v1`
2. 模板来源：
   - `1、专利名称 - 技术交底书v1.docx`（主体）
   - `2、专利名称 - 检索报告v1.doc`（附录）
3. 仅作用于 `disclosure` 产物（`artifacts/disclosure.md`、`artifacts/disclosure.docx`）
4. 保持现有 CLI 选择方式：`--template sansec_disclosure_v1`

### 2.2 非目标（Out of Scope）

1. 不改 `spec_draft` 和 `claims_draft` 模板体系
2. 不改搜索能力（英文扩展、中文站点、自定义站点）  
   说明：搜索为后续子项目 2 单独设计与实施
3. 不改阶段编排与输出目录结构

## 3. 设计决策

### 3.1 方案选择

采用“纯手工抽取法”：

1. 人工阅读 `SansecPatentTempl` 两份源文件
2. 手工重建为项目可用模板：
   - `autopatent/templates/defaults/sansec_disclosure_v1.md.j2`
   - `autopatent/templates/defaults/sansec_disclosure_v1.docx.j2.md`
3. 不新增模板引擎语法，不修改模板加载协议

选择理由：

1. 交付速度最快
2. 风险最低（不引入 `.doc` 解析不确定性）
3. 与现有模板系统完全兼容

### 3.2 模板内容组织

模板统一组织为两段：

1. 主体（技术交底书）
   - 标题与技术领域
   - 背景技术
   - 发明内容与核心方案
   - 实施方式与技术效果
2. 附录（检索报告）
   - 附录标题：`附录A 检索报告要点`
   - 检索范围与依据说明
   - 关键对比结论框架
   - 风险与建议框架

## 4. 占位符与数据映射

模板严格复用当前 `disclosure_context` 可用字段，避免改动渲染引擎。

### 4.1 核心占位符

1. `{{ title }}`
2. `{{ technical_field }}`
3. `{{ background }}`
4. `{{ summary }}`
5. `{{ embodiments }}`

### 4.2 扩展占位符

1. `{{ invention_title }}`
2. `{{ technical_field_cn }}`
3. `{{ background_art }}`
4. `{{ core_solution }}`
5. `{{ technical_effects }}`
6. `{{ embodiments_detail }}`

### 4.3 附录信息字段

1. `{{ evidence_refs }}`
2. `{{ claim_seed_points }}`
3. `{{ code_evidence }}`

说明：当前模板引擎不支持循环语法（`{% ... %}`）。列表字段在模板中以静态说明 + 文本化段落呈现，不依赖循环渲染。

## 5. 系统架构与数据流

### 5.1 组件边界

1. `autopatent/templates/defaults/*`：模板文件载体
2. `autopatent/templates/renderer.py`：模板加载与占位符渲染（不变）
3. `STAGE_07` 渲染阶段：通过 `metadata.template` 指定模板（不新增分支）

### 5.2 运行时流程

1. CLI 接收 `--template sansec_disclosure_v1`
2. `metadata.template` 写入执行上下文
3. `STAGE_07` 调用 `render_disclosure(context, template_name)`
4. 渲染器加载 `sansec_disclosure_v1.*` 模板文件
5. 输出 `artifacts/disclosure.md` 与 `artifacts/disclosure.docx`
6. `STAGE_15` 导出到 `deliverables/` 与 `final_package/`

## 6. 错误处理与回退策略

### 6.1 模板缺失

若 `sansec_disclosure_v1` 文件缺失，沿用现有机制回退 `cn_invention_default`。

### 6.2 占位符缺失

渲染器继续保持当前行为：发现缺失字段时抛出明确错误，避免静默产出错误文档。

### 6.3 回滚

若模板效果不满足预期，仅需移除或替换 `sansec_disclosure_v1` 两个模板文件，不影响其他阶段逻辑。

## 7. 测试与验收

### 7.1 单元测试

1. 新增模板可渲染测试：`template_name="sansec_disclosure_v1"`
2. 断言渲染结果无未替换占位符 `{{ ... }}`
3. 断言包含附录章节标题与关键段落骨架

### 7.2 集成验证

1. 运行：
   `python -m autopatent.cli run --template sansec_disclosure_v1 ...`
2. 断言：
   - `artifacts/disclosure.md` 存在
   - `deliverables/disclosure.md` 存在
   - 文档包含“主体 + 附录A 检索报告要点”结构

### 7.3 验收标准

1. 可通过 `--template` 直接切换
2. 新模板仅影响 `disclosure`
3. 默认模板与既有流程不回归

## 8. 实施清单（子项目 1）

1. 在 `autopatent/templates/defaults/` 新增 `sansec_disclosure_v1.md.j2`
2. 在 `autopatent/templates/defaults/` 新增 `sansec_disclosure_v1.docx.j2.md`
3. 更新 README 的模板选择说明
4. 补充模板渲染与 pipeline smoke 测试

## 9. 后续子项目衔接

本设计仅覆盖模板转换。以下需求进入子项目 2：

1. 扩展英文检索覆盖面
2. 增加中文站点检索
3. 增加自定义站点脚本化接入机制（配置/模板/插件）

