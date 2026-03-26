# AutoPatent 检索插件中枢设计（子项目 2）

日期：2026-03-26  
范围：`STAGE_02 PRIOR_ART_SCAN` 可扩展检索框架升级  
目标形态：可插拔站点接入 + 统一执行内核 + 可选 crawl 回退

## 1. 背景与目标

当前 `STAGE_02` 已支持 `offline/seed-only/online` provider，但站点接入方式仍偏“内置固定逻辑”，扩展新站点需要直接改 provider 代码，维护成本高。

本设计目标：

1. 建立插件目录机制，站点适配能力可独立演进。
2. 建立统一执行内核，统一处理重试、限流、熔断、降级与观测。
3. 在站点直连失败时支持可选抓取工具回退（优先预留 `crawl4ai`）。
4. 保持现有 provider 行为兼容，不破坏当前 CLI 使用方式。

## 2. 范围与非目标

### 2.1 范围（In Scope）

1. 新增 provider：`plugin-hub`（插件中枢）。
2. 新增插件协议、注册表、执行内核与统一输出契约。
3. 首批插件实现：
   - `openalex_plugin`
   - `arxiv_plugin`
   - `semantic_scholar_plugin`
   - `crossref_plugin`
   - `epo_ops_plugin`
4. 新增可选回退执行器：`crawl4ai_runner`。
5. 新增配置项：插件启用集、并发、重试、熔断、回退开关。
6. 新增测试：插件发现、失败降级、输出一致性、兼容性回归。

### 2.2 非目标（Out of Scope）

1. 本轮不承诺所有中文站点稳定直连（CNKI/Wanfang/CQVIP/CNIPA 先进入第二批）。
2. 本轮不引入数据库/消息队列等重型依赖。
3. 本轮不修改 `STAGE_03+` 打分逻辑，只保证输入证据契约兼容。

## 3. 方案选型与决策

选型：**插件 + 统一执行内核（方案 B）**。

选择理由：

1. 插件只聚焦站点协议与解析，执行策略统一收口，避免重复实现。
2. 易于增量扩站点，后续接入复杂站点不需要修改主 provider。
3. 对可观测性友好，便于输出每个插件的成功率与失败原因。

## 4. 架构设计

## 4.1 目录结构

新增模块（相对 `autopatent/search/`）：

1. `plugin_hub.py`：统一执行内核与 `PluginHubProvider`。
2. `plugins/base.py`：插件协议定义（接口/数据模型）。
3. `plugins/registry.py`：内置插件注册与动态加载入口。
4. `plugins/openalex_plugin.py`
5. `plugins/arxiv_plugin.py`
6. `plugins/semantic_scholar_plugin.py`
7. `plugins/crossref_plugin.py`
8. `plugins/epo_ops_plugin.py`
9. `fallback/crawl4ai_runner.py`：可选抓取回退执行器。

## 4.2 运行时数据流

1. `PriorArtScanStage` 调用 `get_search_provider("plugin-hub")`。
2. `PluginHubProvider.collect(...)` 接收 `topic/resources/queries/candidates`。
3. `plugin_hub` 根据 `enabled_plugins` 选择插件并调度执行。
4. 每插件执行统一经过：
   - 请求构建
   - 重试与超时控制
   - 熔断判断
   - 失败时可选 crawl 回退
5. 输出统一 `RawHit` 列表，交给现有 `deduplicate_hits -> summarize_hits`。
6. 将插件级观测信息写入 `search_meta.json`。

## 5. 插件契约（核心）

插件接口最小集合：

1. `plugin_id() -> str`
2. `supports(query: str, topic: str) -> bool`
3. `build_requests(query: str, topic: str, limit: int) -> list[RequestSpec]`
4. `parse_response(payload: str | bytes, request: RequestSpec) -> list[RawHit]`
5. `fallback_urls(query: str, topic: str, limit: int) -> list[str]`
6. `parse_fallback(payload: str, url: str, query: str) -> list[RawHit]`

统一数据模型（逻辑字段）：

1. `RequestSpec`：
   - `method`
   - `url`
   - `headers`
   - `timeout_sec`
   - `meta`（用于解析阶段传参）
2. `RawHit`：
   - `source`
   - `title`
   - `url`
   - `query`
   - `rank`
   - `year`（可选）
   - `doi`（可选）
   - `authors`（可选）
   - `abstract`（可选）

兼容要求：

1. 所有插件返回字段最终必须可映射到现有 `summarize_hits()` 所需字段。
2. 插件不得直接写文件；文件写出统一由 `PriorArtScanStage` 处理。
3. `fallback_urls/parse_fallback` 由插件显式提供，避免 fallback 链路接口歧义。

## 6. 统一执行内核策略

每个插件执行策略：

1. 逐 query 执行（按配置可并发）。
2. 单请求失败后按指数退避重试：`1s -> 2s -> 4s`（可配置）。
3. 连续失败超过阈值触发短期熔断（插件级），避免雪崩重试。
4. 熔断期间插件跳过并记录 `skipped_by_circuit_breaker`。
5. 插件失败后可选调用 `crawl4ai_runner` 做回退抓取。

## 6.1 执行语义（明确约束）

1. `max_workers` 作用域：**请求级并发**（跨插件、跨 query 的统一请求池并发上限）。
2. 调度顺序：按 `enabled_plugins` 顺序遍历插件；插件内部按 query 顺序提交请求。
3. 重试作用域：**单请求级重试**，不重放整个插件或整个 query 批次。
4. 熔断作用域：**插件级熔断**，一个插件熔断不影响其他插件继续执行。
5. 熔断复位：达到 `cooldown_sec` 后自动恢复为半开状态，允许一次探测请求。
6. 结果合并顺序：按插件顺序、query 顺序、rank 升序稳定合并，保证可复现性。

失败处理原则：

1. 单插件失败不应中断 `STAGE_02`。
2. 当全部插件失败时仍产出空证据文件与失败原因元数据，供后续阶段判定。

## 7. crawl 回退设计（可选依赖）

回退触发条件：

1. 插件直连请求失败（网络错误、HTTP 4xx/5xx、解析失败）。
2. 配置 `enable_crawl_fallback=true`。

执行规则：

1. 尝试导入 `crawl4ai`；未安装则记录 `fallback_unavailable` 并继续。
2. 已安装则调用插件的 `fallback_urls(...)` 生成候选 URL，再执行抓取。
3. 抓取结果由同一插件 `parse_fallback(...)` 转换为 `RawHit`。

安全边界：

1. 仅允许 HTTP/HTTPS URL。
2. 单次回退请求限制超时时间与最大内容长度。
3. 回退结果打标 `via_fallback=true` 用于后续审计。

## 8. 配置设计

`config.json` 增加：

1. `search_provider: "plugin-hub"`
2. `search.plugin_hub.enabled_plugins: [str]`
3. `search.plugin_hub.max_workers: int`
4. `search.plugin_hub.request_timeout_sec: int`
5. `search.plugin_hub.retry.max_attempts: int`
6. `search.plugin_hub.retry.backoff_base_sec: float`
7. `search.plugin_hub.circuit_breaker.failure_threshold: int`
8. `search.plugin_hub.circuit_breaker.cooldown_sec: int`
9. `search.plugin_hub.enable_crawl_fallback: bool`
10. `search.plugin_hub.fallback_tool: "crawl4ai"`

默认值与校验规则：

1. `enabled_plugins` 默认：`["openalex", "arxiv", "semantic_scholar", "crossref", "epo_ops"]`
2. `max_workers` 默认 `8`，有效范围 `[1, 64]`
3. `request_timeout_sec` 默认 `20`，有效范围 `[3, 120]`
4. `retry.max_attempts` 默认 `3`，有效范围 `[1, 6]`
5. `retry.backoff_base_sec` 默认 `1.0`，有效范围 `(0, 10]`
6. `circuit_breaker.failure_threshold` 默认 `3`，有效范围 `[1, 20]`
7. `circuit_breaker.cooldown_sec` 默认 `120`，有效范围 `[10, 3600]`
8. `fallback_tool` 当前仅支持 `"crawl4ai"`；其他值视为配置错误并在启动时拒绝。
9. `enabled_plugins` 含未知插件 ID 时：启动失败并给出未知 ID 列表（fail-fast）。

兼容策略：

1. 不提供 `search.plugin_hub` 时走默认值。
2. 旧配置（`offline/seed-only/online`）保持原行为。

## 9. 可观测性与产物

`search_meta.json` 新增字段：

1. `provider: "plugin-hub"`
2. `plugins`: 每插件统计（`success`, `failed`, `skipped`, `fallback_used`）
3. `circuit_breaker`: 熔断次数与触发插件列表
4. `errors_sample`: 截断错误样本（避免日志爆炸）

计数口径（避免歧义）：

1. `success`：插件返回至少 1 条 `RawHit` 的请求次数（请求级）。
2. `failed`：请求最终失败次数（已含重试耗尽，且无 fallback 成功）。
3. `skipped`：因插件熔断或 `supports=false` 被跳过的请求次数。
4. `fallback_used`：触发 fallback 且产出至少 1 条 `RawHit` 的请求次数。

`prior_art_evidence.jsonl` 增量字段：

1. `plugin_id`
2. `via_fallback`

## 10. 首批插件定义

## 10.1 第一批（本轮实施）

1. OpenAlex（论文元数据主源）
2. arXiv（预印本补充）
3. Semantic Scholar（相关性补充）
4. Crossref（DOI 元数据补齐）
5. EPO OPS（专利维度补充）

EPO OPS 凭据策略：

1. 使用环境变量：`EPO_OPS_CONSUMER_KEY`、`EPO_OPS_CONSUMER_SECRET`。
2. 未配置凭据时，`epo_ops_plugin` 自动标记为 `skipped_no_credentials`，不阻断 `STAGE_02`。
3. CI 验收不要求 EPO 实际联网成功，但要求跳过行为与元数据记录正确。

## 10.2 第二批（后续）

1. CNIPA
2. CNKI
3. Wanfang
4. CQVIP
5. Google Patents HTML

## 11. 测试与验收

## 11.1 单元测试

1. 插件注册与发现。
2. 插件契约校验（返回字段合法性）。
3. 内核重试/熔断逻辑。
4. fallback 可用/不可用分支。

## 11.2 集成测试

1. `search_provider=plugin-hub` 可产出 `prior_art_evidence.jsonl`。
2. 某插件故障时 pipeline 不中断。
3. 全插件失败时仍输出 `search_meta.json` 且含失败原因。

## 11.3 验收标准

1. 不改 CLI 参数即可启用新 provider（通过 config）。
2. 首批 5 个插件可独立启停。
3. `STAGE_02 -> STAGE_03` 链路兼容。
4. 全量测试通过，不回归现有 `offline/seed-only/online`。
5. 统计一致性：`success + failed + skipped >= query_count * enabled_plugin_count`（考虑重试后按最终请求结果计数）。
6. fallback 可观测：当 fallback 开启且直连失败时，`fallback_used > 0` 或 `fallback_unavailable` 明确记录。

## 12. 风险与缓解

1. 外部站点频繁变更：通过插件隔离和快速替换降低影响面。
2. 回退抓取性能开销：通过回退开关、阈值和超时限制控制成本。
3. 站点限流导致不稳定：通过插件级熔断与统计观测降低抖动。

## 13. 里程碑与交付

1. M1：插件协议与内核框架落地（含配置与基础测试）。
2. M2：首批 5 插件接入完成（含失败回退与观测）。
3. M3：文档与示例配置完善，完成回归测试并发布。
