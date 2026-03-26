# AutoPatent

AutoPatent 是一个面向中国发明专利撰写流程的自动化程序。

当前仓库阶段：CN MVP 可运行版本。`run` 命令已接通 `STAGE_00` 到 `STAGE_15` 的执行链路，后半程阶段目前仍以确定性 stub 为主。

## 当前实现范围

本仓库目前仅实现中国发明专利自动化流程的 MVP 版本，聚焦交底书与审查意见预案导出链路，不包含海外制度或法律规则引擎。  
当前实现重点是“可恢复的阶段化执行框架 + 最小可用产物导出”，复杂检索与法律校验逻辑仍会在后续迭代补全。
当前 `STAGE_02` 支持检索 provider 选择：默认 `offline`，可切换 `seed-only` 或 `online`（真实联网检索 OpenAlex + arXiv）。
当前 `STAGE_02` 支持通过配置文件 `search_provider` 或环境变量 `AUTOPATENT_SEARCH_PROVIDER` 覆盖 provider。
当前已支持可选 LLM 生成链路（`STAGE_07/10/11/14`）：未配置 LLM 时自动回退到本地 stub 文本。
当前 LLM 生成文本会经过清洗：自动去除“以下为关于…/如需我继续…”等助手式临时话术，输出面向正式文档。
当前图示产物按优先级生成：ASCII（必产）→ Mermaid（必产）→ PNG（可选，依赖 `mmdc`）。

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

`--auto-approve` 会跳过 Stage 04 命令行选题，直接按预选方向继续执行。若要人工选题，不要带该参数。

3. 文档 + 代码目录输入：

```
python -m autopatent.cli run --input-doc ./seed.md --code-dir ./impl --auto-approve
```

4. 中断后继续执行：

```
python -m autopatent.cli run --topic "示例主题" --output ./artifacts/demo --resume --auto-approve
```

`--resume` 会优先读取阶段 metadata 快照；若快照缺失，会回退到 `metadata_latest.json`，并尝试从 `human_decisions.json` 恢复 Stage 04 选择。
执行完成后，CLI 会在终端打印 `Stage outputs summary`，按 `STAGE_00..STAGE_15` 展示阶段名称与产物路径，便于快速核对每阶段输出。

## 配置文件（可选）

`run` 支持 `--config` 指定 JSON 配置文件。示例：

```json
{
  "checkpoint_root": "./state",
  "search_provider": "online",
  "llm": {
    "provider": "openai-compatible",
    "base_url": "http://10.20.35.182:13456/v1",
    "api_key_env": "OPENAI_API_KEY",
    "model": "gpt-5.4",
    "timeout_sec": 60,
    "max_tokens": 4096,
    "temperature": 0.2
  }
}
```

`search_provider` 可选值：
- `offline`：离线伪检索（稳定、无网络依赖）
- `seed-only`：仅基于输入主题/seed生成最小证据
- `online`：真实联网检索（OpenAlex + arXiv）

运行方式：

```bash
export OPENAI_API_KEY="your-api-key"
python -m autopatent.cli run --config ./config.json --topic "示例主题" --output ./artifacts/demo --auto-approve
```

若希望在 Stage 04 人工选题，去掉 `--auto-approve`，按提示输入例如 `choose 2`。

## Mermaid 图片渲染依赖（mmdc）

`STAGE_06` 会始终生成 ASCII 与 Mermaid 图文件；若安装 `mmdc`，还会继续生成 PNG 图片。

依赖要求：
- Node.js >= 18（当前环境建议 20+）
- npm
- `@mermaid-js/mermaid-cli`（命令名 `mmdc`）

安装方式：

```bash
npm install -g @mermaid-js/mermaid-cli
```

验证安装：

```bash
mmdc --version
```

快速验证渲染：

```bash
cat > /tmp/quick.mmd <<'EOF'
flowchart TD
    A[Start] --> B[Done]
EOF

mmdc -i /tmp/quick.mmd -o /tmp/quick.png
```

若使用 root 执行且遇到 Chromium sandbox 错误，可改用：

```bash
cat > /tmp/puppeteer-config.json <<'EOF'
{
  "args": ["--no-sandbox", "--disable-setuid-sandbox"]
}
EOF

mmdc -p /tmp/puppeteer-config.json -i /tmp/quick.mmd -o /tmp/quick.png
```

说明：AutoPatent 在调用 `mmdc` 生成 PNG 时，检测到 root 用户会自动附加 `--no-sandbox` 参数，无需手工干预。

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
12. `./artifacts/demo/artifacts/disclosure_outline.md`
13. `./artifacts/demo/artifacts/system_architecture.md`
14. `./artifacts/demo/artifacts/process_stages.md`
15. `./artifacts/demo/artifacts/figures_and_tables_plan.md`
16. `./artifacts/demo/artifacts/architecture_ascii.txt`
17. `./artifacts/demo/artifacts/process_flow_ascii.txt`
18. `./artifacts/demo/artifacts/architecture.mmd`
19. `./artifacts/demo/artifacts/process_flow.mmd`
20. `./artifacts/demo/artifacts/architecture.png`（当环境安装 `mmdc` 时）
21. `./artifacts/demo/artifacts/process_flow.png`（当环境安装 `mmdc` 时）
22. `./artifacts/demo/deliverables/disclosure_validation_report.md`
23. `./artifacts/demo/deliverables/system_architecture.md`
24. `./artifacts/demo/deliverables/process_stages.md`
25. `./artifacts/demo/deliverables/figures_and_tables_plan.md`
26. `./artifacts/demo/deliverables/architecture_ascii.txt`
27. `./artifacts/demo/deliverables/process_flow_ascii.txt`
28. `./artifacts/demo/deliverables/architecture.mmd`
29. `./artifacts/demo/deliverables/process_flow.mmd`
30. `./artifacts/demo/final_package/`
31. `./artifacts/demo/artifacts/prior_art_queries.json`
32. `./artifacts/demo/artifacts/search_meta.json`
33. `./artifacts/demo/artifacts/input_doc_digest.md`（当传入 `--input-doc` 时）
34. `./artifacts/demo/artifacts/code_inventory.json`（当传入 `--code-dir` 时）
35. `./artifacts/demo/stage_outputs/STAGE_XX/manifest.json`（每阶段输出清单）
36. `./artifacts/demo/stage_outputs/STAGE_XX/files/`（该阶段新增或变更文件快照）

## 默认模板行为

当命令行未显式提供 `--template` 参数时，CLI 会隐式使用 `cn_invention_default` 模板继续执行，不会中断流程或报错。

## `sansec_disclosure_v1` 模板用法

可通过 `--template sansec_disclosure_v1` 启用 Sansec 交底书模板：

```bash
python -m autopatent.cli run \
  --topic "抗量子SSL和证书" \
  --template sansec_disclosure_v1 \
  --output /tmp/autopatent-sansec-smoke \
  --auto-approve
```

作用范围说明：
- `sansec_disclosure_v1` 仅影响 disclosure 产物生成（如 `disclosure.md`/`disclosure.docx` 的内容组织）。
- 不影响 `spec_draft` 与 `claims_draft` 的生成逻辑或输出语义。

模板语义说明：
- 交底书正文按“技术交底书主体”结构组织。
- 在交底书中追加“附录A 检索报告要点”（检索报告附录A）。

验收建议（smoke）：
- 运行上述命令后，检查 `/tmp/autopatent-sansec-smoke/artifacts/disclosure.md` 文件存在。
- 文件内容应包含标题文本“附录A 检索报告要点”。
