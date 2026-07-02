---
name: web-search
version: 1.0.0
description: "联网搜索：用开源、免付费-key 的后端做实时网页搜索，返回干净的标题/URL/摘要列表供 agent 消费。后端优先自托管 SearXNG（设 SEARXNG_URL，全离线、无量限、聚合多引擎），未配置时自动回退 DuckDuckGo（`ddgs` 开源库，零配置免 key）。当用户/任务需要查询实时信息、当前事件、最新文档、事实核查、查某个库/产品/人/公司的公开资料、或 agent 需要在生成前先联网检索证据时使用。只做「搜索并返回结果列表」；抓取单个网页全文请另用 fetch/browse 类能力。"
metadata:
  requires:
    bins: ["uv"]
  cliHelp: "uv run scripts/web_search.py --help"
  env:
    SEARXNG_URL: "可选。自托管 SearXNG 实例地址，如 http://localhost:8080。设了就走 SearXNG，否则回退 DuckDuckGo。"
    SEARXNG_LANGUAGE: "可选。SearXNG 结果语言，如 zh-CN / en。"
    SEARXNG_CATEGORIES: "可选。SearXNG 分类，默认 general。"
---

# web-search

给 OpenClaw agent 提供**联网搜索**能力。全开源、无需任何付费 API key。

## 核心概念

- 单一入口脚本 [`scripts/web_search.py`](scripts/web_search.py)，用 `uv run` 执行会自动装依赖（`ddgs`），无需预装。
- 两个后端，均开源、免 key：
  - **searxng**（推荐生产）：查询自托管 [SearXNG](https://github.com/searxng/searxng) 的 JSON API。无量限、可完全离线、聚合 Google/Bing/DDG 等多引擎。设环境变量 `SEARXNG_URL` 即启用。
  - **ddg**（默认回退）：通过开源 `ddgs` 库走 DuckDuckGo。零配置、免 key，适合快速使用或没有 SearXNG 时。
- 后端选择默认 `auto`：**有 `SEARXNG_URL` 就用 SearXNG，否则用 DuckDuckGo**。也可用 `--backend searxng|ddg` 强制。
- 输出：`--format md`（默认，人读）或 `--format json`（`[{title,url,content}]`，程序消费）。

## 快速用法

```bash
# 默认：5 条结果，markdown
uv run scripts/web_search.py "问对云智科技 融资"

# 8 条，JSON（agent 程序化消费）
uv run scripts/web_search.py "latest Claude model pricing" -n 8 --format json

# 强制某后端 / 调超时
uv run scripts/web_search.py "SearXNG docker compose" --backend ddg --timeout 20
```

启用 SearXNG（推荐，无量限、更稳）：

```bash
export SEARXNG_URL="http://localhost:8080"      # 你的自托管实例
uv run scripts/web_search.py "..."               # 自动走 SearXNG
```

没有 SearXNG？见 [`references/backends.md`](references/backends.md) 里的一段 docker-compose 5 分钟起一个。

## 退出码

| code | 含义 |
|---|---|
| 0 | 成功，有结果 |
| 2 | 用法错误（空查询 / `-n` 越界） |
| 3 | 查询成功但无结果 |
| 4 | 后端/网络错误（超时、连不上、依赖缺失） |

Agent 应根据退出码决策：`3` 可换关键词重搜；`4` 可提示检查 `SEARXNG_URL` 或网络。

## 备注

- 不带 `uv` 也能跑：`python3 scripts/web_search.py ...`，但 `ddg` 后端需先 `pip install ddgs`；`searxng` 后端仅用标准库，任意 Python 3.10+ 即可。
- 本 skill 只负责「搜索 → 结果列表」。要读取某条结果的网页全文，交给 fetch/browse 类能力。
- 后端细节、SearXNG 部署、返回字段说明见 [`references/backends.md`](references/backends.md)。
