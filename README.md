# AutoPatent

AutoPatent 是一个面向中国发明专利撰写流程的自动化程序。

当前仓库阶段：CN MVP 可运行版本。`run` 命令已接通 `STAGE_00` 到 `STAGE_15` 的执行链路，后半程阶段目前仍以确定性 stub 为主。

## 当前实现范围

本仓库目前仅实现中国发明专利自动化流程的 MVP 版本，聚焦交底书与审查意见预案导出链路，不包含海外制度或法律规则引擎。  
当前实现重点是“可恢复的阶段化执行框架 + 最小可用产物导出”，复杂检索与法律校验逻辑仍会在后续迭代补全。
当前 `STAGE_02` 已具备离线检索管线（查询扩展、去重、证据摘要），默认使用本地确定性 pseudo-hits，不访问外网。

## 快速开始

以下示例为当前可执行用法：

1. 交互式运行（默认，Stage 04 需要输入 `choose <id>`）：

```
python -m autopatent.cli run --topic "示例主题" --output ./artifacts/demo
```

2. 自动批准运行（非交互）：

```
python -m autopatent.cli run --topic "示例主题" --output ./artifacts/demo --auto-approve
```

3. 文档 + 代码目录输入：

```
python -m autopatent.cli run --input-doc ./seed.md --code-dir ./impl --auto-approve
```

4. 中断后继续执行：

```
python -m autopatent.cli run --topic "示例主题" --output ./artifacts/demo --resume --auto-approve
```

## 输出目录说明

以 `--output ./artifacts/demo` 为例，当前会产出：

1. `./artifacts/demo/deliverables/disclosure.md`
2. `./artifacts/demo/deliverables/disclosure.docx`（当前为 stub 文本载荷）
3. `./artifacts/demo/deliverables/oa_response_playbook.md`
4. `./artifacts/demo/state/checkpoint_history.json`
5. `./artifacts/demo/state/metadata_latest.json`
6. `./artifacts/demo/state/metadata/STAGE_XX.json`（各阶段快照）
7. `./artifacts/demo/state/human_decisions.json`（人工关卡决策记录）
8. `./artifacts/demo/artifacts/direction_analysis_report.md`
9. `./artifacts/demo/artifacts/prior_art_evidence.jsonl`
10. `./artifacts/demo/artifacts/direction_scores.json`
11. `./artifacts/demo/artifacts/disclosure_context.json`
12. `./artifacts/demo/deliverables/disclosure_validation_report.md`
13. `./artifacts/demo/final_package/`
14. `./artifacts/demo/artifacts/prior_art_queries.json`
15. `./artifacts/demo/artifacts/search_meta.json`

## 默认模板行为

当命令行未显式提供 `--template` 参数时，CLI 会隐式使用 `cn_invention_default` 模板继续执行，不会中断流程或报错。
