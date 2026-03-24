# AutoPatent CN MVP 设计说明（Brainstorming 确认稿）

日期：2026-03-24  
范围：仅中国发明专利方向（MVP）  
语言：中文输出

实现状态（2026-03-24）：MVP 代码骨架已落地，当前测试集 `pytest -v` 共 30 项通过。

说明：本文档是 CN MVP 的目标设计说明，部分章节描述的是目标能力与阶段契约，不等同于“全部已完整实现”。

## 1. 目标与范围

AutoPatent 是一个面向专利撰写流程的自动化程序，目标是将用户输入（主题/技术文档/技术文档+代码目录）转化为：

1. 专利草案包
2. 校验报告
3. 审查意见答复预案

MVP 只覆盖中国发明专利，不扩展美国/EPO/JPO 规则。

## 2. 输入与运行模式

### 2.1 输入模式（全部支持）

1. 仅主题输入（topic only）
2. 技术文档输入（例如已有技术规范、论文草稿）
3. 技术文档 + 代码目录输入（用于补充技术证据和实施细节）

### 2.2 CLI 运行原则

1. 支持交互式选择（核心）
2. 支持自动批准（非关键确认可跳过）
3. 支持中断恢复（resume）

## 3. 阶段框架（V3）

共 16 个阶段（`STAGE_00` 到 `STAGE_15`）：

1. `STAGE_00 INPUT_INGEST`  
统一摄入输入，标准化主题、文档、代码路径与元数据。

2. `STAGE_01 DIRECTION_DISCOVERY`  
自动发现专利方向候选（数量动态，通常约 5 个）。

3. `STAGE_02 PRIOR_ART_SCAN`  
执行专利/论文检索，产出证据池。

4. `STAGE_03 DIRECTION_SCORING`  
对方向进行评分（新颖性风险、可实施性、证据充分性、产业价值）。

5. `STAGE_04 HUMAN_DIRECTION_GATE`  
CLI 人工选择关卡；弱质量自动扩检，最多 3 轮。

6. `STAGE_05 TITLE_FINALIZATION`  
确定题目与主保护点表述。

7. `STAGE_06 DISCLOSURE_OUTLINE`  
技术交底书大纲生成。

8. `STAGE_07 DISCLOSURE_DRAFT`  
技术交底书正文生成（Markdown + DOCX）。

9. `STAGE_08 DISCLOSURE_VALIDATE`  
交底书完整性与可专利性链路校验。

10. `STAGE_09 CLAIM_STRATEGY`  
权利要求布局策略（主权 + 从权分层）。

11. `STAGE_10 CLAIMS_DRAFT`  
权利要求书草案生成。

12. `STAGE_11 SPEC_DRAFT`  
说明书草案生成（背景、发明内容、附图说明、具体实施方式）。

13. `STAGE_12 PATENT_LEGAL_VALIDATE`  
法律与格式规则校验（CN 口径）。

14. `STAGE_13 NOVELTY_RISK_REVIEW`  
新颖性/创造性风险复核，形成风险说明。

15. `STAGE_14 OA_RESPONSE_PREP`  
审查意见答复预案与证据映射生成。

16. `STAGE_15 PACKAGE_EXPORT`  
统一导出交付包。

## 4. 技术交底书模板系统（已确认）

### 4.1 模板分层

1. `base`：通用章节骨架与必填规则
2. `profile`：专利类型场景模板（MVP 先提供 `cn_invention_default`）
3. `project_override`：项目覆盖层（自定义字段、章节与措辞风格）

### 4.2 默认模板行为（新增确认项）

当用户未显式指定模板时，系统必须自动使用内置默认模板：

`cn_invention_default`

即 CLI 无 `--template` 参数时，不报错，不阻断流程，直接走内置模板渲染。

### 4.3 统一上下文模型

模板渲染统一依赖 `disclosure_context.json`，核心字段包括：

1. `invention_title`
2. `technical_field`
3. `background_art`
4. `problems_to_solve`
5. `core_solution`
6. `technical_effects`
7. `embodiments`
8. `optional_figures_desc`
9. `claim_seed_points`
10. `evidence_refs`
11. `code_evidence`

### 4.4 导出格式

1. `disclosure.md`
2. `disclosure.docx`
3. `disclosure_validation_report.md`

## 5. CLI 交互协议（已确认）

### 5.1 方向关卡交互（Stage 04）

每个候选方向展示：

1. 方向标题
2. 创新点摘要
3. 主要风险
4. 证据数量
5. 综合评分

支持命令：

1. `choose <id>`
2. `expand`
3. `merge <id1,id2>`
4. `drop <id>`
5. `quit`

### 5.2 动态候选数量

候选数量不固定为 5，目标约 5：

1. 候选少时可低于 5
2. 候选多时可高于 5
3. 由检索证据质量与聚类结果决定

### 5.3 弱质量自动重试

当方向整体质量不足时：

1. 自动触发 `expand` 检索
2. 最多重试 3 轮
3. 超限后必须进入人工决策（继续/终止/改题）

### 5.4 Resume 行为（目标设计，待完整实现）

1. 目标行为：每阶段写入 checkpoint
2. 目标行为：`--resume` 从最近失败或中断阶段继续
3. 目标行为：已确认的人类决策写入 `human_decisions.json`
4. 当前状态：CLI 已预留 `--resume` 参数形态，完整 checkpoint / decision 恢复语义仍在后续任务中实现

## 6. 检索资源与策略（MVP）

### 6.1 重点检索站点（首批）

专利：

1. CNIPA 检索系统
2. WIPO PATENTSCOPE
3. EPO Espacenet
4. USPTO
5. Google Patents

论文：

1. Google Scholar
2. Semantic Scholar
3. arXiv
4. IEEE Xplore
5. ACM Digital Library
6. CNKI
7. Wanfang
8. CQVIP

### 6.2 检索处理链

1. 从技术要素自动扩展查询词
2. 多源并发检索与重试
3. 专利/论文去重
4. 证据摘要与可追溯引用
5. 供方向评分、交底书和权利要求阶段复用

## 7. 关键产物清单

1. `direction_analysis_report.md`
2. `prior_art_evidence.jsonl`
3. `direction_scores.json`
4. `disclosure_context.json`
5. `disclosure.md`
6. `disclosure.docx`
7. `disclosure_validation_report.md`
8. `claims_draft.md`
9. `spec_draft.md`
10. `novelty_risk_report.md`
11. `oa_response_playbook.md`
12. `final_package/`

## 8. MVP 验收标准

1. 三种输入模式均可跑通到导出阶段
2. 未指定模板时自动使用 `cn_invention_default`
3. Stage 04 支持 CLI 人工选择与 `expand` 自动重试（最多 3 次）
4. 输出包含：草案包 + 校验报告 + OA 预案
5. 中断后 `--resume` 可正确续跑，不丢失人工决策

## 9. 非目标（MVP 不做）

1. 非中文文书输出
2. 多法域法律规则引擎
3. 全自动图纸绘制与审查格式排版细节
4. 诉讼级 FTO 法律意见替代
