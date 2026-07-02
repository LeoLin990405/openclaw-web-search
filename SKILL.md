---
name: web-search
version: 1.2.0
description: "联网搜索 + 抓取：用开源、免付费-key 的后端做实时网页搜索并读取网页正文，供 agent 消费。search 返回干净的标题/URL/摘要列表（后端优先自托管 SearXNG，设 SEARXNG_URL 全离线无量限，未配置自动回退 DuckDuckGo 开源库零配置免 key）；fetch 把某条结果的网页抓成干净 Markdown（或 JSON API 直出 JSON）。当用户/任务需要查询实时信息、当前事件、天气、股价/行情、最新文档、事实核查、查某个库/产品/人/公司的公开资料，或 agent 需要在生成前先联网检索证据、再读进具体页面拿到确切数值时使用。典型闭环：先 web_search 拿权威链接 → 再 web_fetch 读该链接正文/接口拿实际数据。"
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

给 OpenClaw agent 提供**联网搜索 + 网页抓取**能力。全开源、无需任何付费 API key。

两个脚本，配成完整闭环：

| 脚本 | 作用 | 依赖(uv 自动装) |
|---|---|---|
| [`scripts/web_search.py`](scripts/web_search.py) | 搜索 → 返回 `[{title,url,content}]` | `ddgs` |
| [`scripts/web_fetch.py`](scripts/web_fetch.py) | 抓某个 URL → 干净 Markdown / JSON | `trafilatura` |

**典型用法**：`web_search` 拿到权威链接 → `web_fetch` 读该链接的正文或接口，拿到确切数值（天气、股价、最新数据等搜索摘要给不了的东西）。

## 核心概念（search）

- 入口脚本 [`scripts/web_search.py`](scripts/web_search.py)，用 `uv run` 执行会自动装依赖（`ddgs`），无需预装。
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

## 抓取（fetch）

读取某个 URL 的正文，供 agent 拿搜索摘要给不了的确切内容/数值：

```bash
# 网页文章 -> 干净 Markdown（去导航/广告/模板）
uv run scripts/web_fetch.py "https://example.com/article"

# 数据接口 -> 直出 JSON（天气/行情等 API）
uv run scripts/web_fetch.py "https://push2.eastmoney.com/api/qt/stock/get?..."

# 纯文本 / 截断长页
uv run scripts/web_fetch.py "URL" --format text --max-chars 8000
```

- JSON 响应 → 美化 JSON；HTML → trafilatura 抽正文转 Markdown（抽不到主正文时自动回退全文 `html2txt`）；自动探测编码（含中文站常见 GBK）；自动解压 `gzip`/`deflate` 响应。
- **二进制内容**（PDF/图片/压缩包/音视频等 `application/*`、`image/*`…）会被识别并**干净报错(EXIT=2)**，不会吐乱码。这类内容请交给对应的解析能力（如 PDF skill）。
- 退出码：`0` 成功 / `2` 用法或不支持的二进制内容 / `3` 空内容 / `4` 抓取失败。
- **适用范围**：面向**文章页 / 内容页 / 数据接口**。网站**首页、导航页、重 JS 的 SPA** 可能抽取稀疏或拿不到动态数据——这类优先用 `web_fetch` 打其背后的 JSON 接口，或改用 browser 类能力。

## 备注

- 不带 `uv` 也能跑：`python3 scripts/web_search.py ...` / `web_fetch.py ...`，但需先 `pip install ddgs trafilatura`；`web_search` 的 `searxng` 后端仅用标准库，任意 Python 3.10+ 即可。
- 后端细节、SearXNG 部署、返回字段说明见 [`references/backends.md`](references/backends.md)。
