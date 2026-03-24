# AutoPatent

AutoPatent 是一个面向中国发明专利撰写流程的自动化程序。

当前仓库阶段：MVP 骨架已实现（阶段组件与测试已落地），CLI `run` 仍处于占位执行阶段。

## 当前实现范围

本仓库目前仅实现中国发明专利自动化流程的 MVP 版本，聚焦交底书、权利要求与审查意见生成链路，不包含海外制度或包装交付环境。  
当前 CLI 以“可运行骨架”为主，后续会逐步补全高级参数的实质执行逻辑。

## 快速开始

以下示例覆盖当前 CLI 参数形态（用于占位执行与参数校验）：

1. 主题驱动：

```
python -m autopatent.cli run --topic "示例主题" --output ./artifacts/demo
```

2. 文档+代码触发（参数形态）：

```
python -m autopatent.cli run --input-doc ./seed.md --code-dir ./impl --resume
```

## 默认模板行为

当命令行未显式提供 `--template` 参数时，CLI 会隐式使用 `cn_invention_default` 模板继续执行，不会中断流程或报错。
