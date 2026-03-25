# AutoPatent

AutoPatent 是一个面向中国发明专利撰写流程的自动化程序。

当前仓库阶段：CN MVP 可运行版本。`run` 命令已接通 `STAGE_00` 到 `STAGE_15` 的执行链路，后半程阶段目前仍以确定性 stub 为主。

## 当前实现范围

本仓库目前仅实现中国发明专利自动化流程的 MVP 版本，聚焦交底书与审查意见预案导出链路，不包含海外制度或法律规则引擎。  
当前实现重点是“可恢复的阶段化执行框架 + 最小可用产物导出”，复杂检索与法律校验逻辑仍会在后续迭代补全。

## 快速开始

以下示例为当前可执行用法：

1. 主题驱动运行：

```
python -m autopatent.cli run --topic "示例主题" --output ./artifacts/demo
```

2. 文档 + 代码目录输入：

```
python -m autopatent.cli run --input-doc ./seed.md --code-dir ./impl --resume
```

3. 中断后继续执行：

```
python -m autopatent.cli run --topic "示例主题" --output ./artifacts/demo --resume
```

## 输出目录说明

以 `--output ./artifacts/demo` 为例，当前会产出：

1. `./artifacts/demo/deliverables/disclosure.md`
2. `./artifacts/demo/deliverables/oa_response_playbook.md`
3. `./artifacts/demo/state/checkpoint_history.json`
4. `./artifacts/demo/state/metadata_latest.json`
5. `./artifacts/demo/state/metadata/STAGE_XX.json`（各阶段快照）

## 默认模板行为

当命令行未显式提供 `--template` 参数时，CLI 会隐式使用 `cn_invention_default` 模板继续执行，不会中断流程或报错。
