# openclaw-web-search

> An [OpenClaw](https://docs.openclaw.ai/) skill that gives agents **web search + web fetch** — using only open-source, no-paid-key backends.
> 一个 [OpenClaw](https://docs.openclaw.ai/) 技能，给 agent 提供**联网搜索 + 网页抓取**能力——全部使用开源、免付费-key 的后端。

[![tests](https://github.com/LeoLin990405/openclaw-web-search/actions/workflows/tests.yml/badge.svg)](https://github.com/LeoLin990405/openclaw-web-search/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.7.0-green.svg)](https://github.com/LeoLin990405/openclaw-web-search/releases)
[![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)](scripts/web_search.py)

---

## 目录 · Contents

- [What it does · 功能](#what-it-does--功能)
- [Install · 安装](#install--安装)
- [Usage · 用法](#usage--用法)
- [Options · 选项](#options--选项)
- [Exit codes · 退出码](#exit-codes--退出码)
- [Behavior notes · 行为说明](#behavior-notes--行为说明)
- [Project structure · 项目结构](#project-structure--项目结构)
- [Tests · 测试](#tests--测试)
- [License · 许可证](#license--许可证)

---

## What it does · 功能

| Script · 脚本 | Does · 作用 | Backend (auto-installed via `uv`) · 后端（`uv` 自动装） |
|---|---|---|
| `scripts/web_search.py` | Search the web → results list · 搜索 → 结果列表 | [`ddgs`](https://github.com/deedy5/ddgs) (DuckDuckGo) or self-hosted [SearXNG](https://github.com/searxng/searxng) |
| `scripts/web_fetch.py` | Read a URL → clean Markdown / JSON · 抓 URL → 干净 Markdown / JSON | [`trafilatura`](https://github.com/adbar/trafilatura) |

Typical loop: **search** for authoritative links → **fetch** the link to get the actual content/values (weather, quotes, latest data) that search snippets don't contain.

典型闭环：先用 **search** 拿到权威链接 → 再用 **fetch** 读该链接，拿到搜索摘要给不了的确切内容/数值（天气、行情、最新数据）。

---

## Install · 安装

```bash
git clone https://github.com/LeoLin990405/openclaw-web-search ~/.openclaw/skills/web-search
```

Requires [`uv`](https://github.com/astral-sh/uv) (scripts auto-install their Python deps). Plain `python3 ≥ 3.10` also works after `pip install ddgs trafilatura`.

需要 [`uv`](https://github.com/astral-sh/uv)（脚本会自动安装 Python 依赖）。也可用纯 `python3 ≥ 3.10`，先 `pip install ddgs trafilatura` 即可。

---

## Usage · 用法

```bash
S=~/.openclaw/skills/web-search/scripts

# search (DuckDuckGo, no setup) · 搜索（DuckDuckGo，零配置）
uv run $S/web_search.py "your query" -n 5
uv run $S/web_search.py "breaking news" --recent d --region us-en --format json

# search via self-hosted SearXNG (no rate limit, offline-capable) · 走自托管 SearXNG（无量限、可离线）
export SEARXNG_URL="http://localhost:8080"
uv run $S/web_search.py "your query"

# fetch as Markdown / data API as JSON / with provenance · 抓正文 / 接口 JSON / 带溯源
uv run $S/web_fetch.py "https://example.com/article"
uv run $S/web_fetch.py "https://d1.weather.com.cn/sk_2d/101020100.html" -H "Referer: http://www.weather.com.cn/"
uv run $S/web_fetch.py "https://arxiv.org/abs/1706.03762" --json
```

Both `--format json` (search) and `--json` (fetch) return a provenance envelope: the payload plus metadata (`elapsed_ms`, backend/status/final_url, …).

两个脚本的 `--format json`（search）与 `--json`（fetch）都返回带溯源的**信封**：正文数据 + 元数据（`elapsed_ms`、后端/状态码/最终 URL 等）。

---

## Options · 选项

### `web_search.py`

| Option · 选项 | Default · 默认 | Meaning · 说明 |
|---|---|---|
| `-n, --num` | `5` | max results (1–50) · 最大结果数 |
| `--format md\|json` | `md` | `json` = envelope `{query, backend, count, elapsed_ms, results}` · 信封 |
| `--backend auto\|searxng\|ddg` | `auto` | `auto` = SearXNG if `SEARXNG_URL` set, else DuckDuckGo · 有 URL 走 SearXNG 否则 DDG |
| `--recent d\|w\|m\|y` | — | only last day/week/month/year · 只要最近一天/周/月/年 |
| `--region` | `wt-wt` | ddg region, e.g. `us-en`, `cn-zh`, `jp-jp` · ddg 地域 |
| `--safesearch on\|moderate\|off` | `moderate` | ddg safe-search level · 安全搜索级别 |
| `--timeout` / `--retries` | `15` / `2` | timeout (s) / retries on 429/5xx/network · 超时 / 重试 |

### `web_fetch.py`

| Option · 选项 | Default · 默认 | Meaning · 说明 |
|---|---|---|
| `--format md\|text` | `md` | HTML → Markdown (keeps links) or plain text · Markdown（保留链接）或纯文本 |
| `--json` | off | envelope `{url, final_url, status, content_type, kind, chars, truncated, elapsed_ms, content}` · 信封 |
| `-H, --header` | — | extra request header, repeatable (Referer / Authorization / Cookie) · 自定义请求头，可重复 |
| `--max-chars` | `0` | truncate output (`0` = no limit) · 截断输出（`0` 不限） |
| `--timeout` / `--retries` | `20` / `2` | timeout (s) / retries on 429/5xx/network · 超时 / 重试 |

**Environment (SearXNG) · 环境变量:** `SEARXNG_URL`, `SEARXNG_LANGUAGE`, `SEARXNG_CATEGORIES`.

---

## Exit codes · 退出码

| Code · 码 | Meaning · 含义 |
|---|---|
| `0` | success · 成功 |
| `2` | usage error / unsupported (binary, bad header/scheme) · 用法错误 / 不支持（二进制、坏头/scheme） |
| `3` | no results / empty content · 无结果 / 空内容 |
| `4` | backend or network error (timeout, unreachable, dep missing) · 后端或网络错误 |

---

## Behavior notes · 行为说明

- **Encoding · 编码** — charset auto-detected (header → `<meta>` → UTF-8 → GBK → latin-1); `gzip`/`deflate` auto-decompressed; non-ASCII URLs percent-encoded (IRI→URI). · 自动探测编码、解压 gzip/deflate、非 ASCII URL 自动编码。
- **Binary content · 二进制内容** — PDF/images/archives/media are rejected cleanly (exit 2) — no mojibake; use a dedicated parser. · 二进制内容干净报错（退出 2），不吐乱码；请交给对应解析器。
- **Scope · 适用范围** — `web_fetch` targets article/content pages and data APIs. Homepages and JS-heavy SPAs may extract sparsely — fetch their backing JSON API, or use a browser tool. · 面向文章页/内容页/数据接口；首页与重 JS 的 SPA 抽取稀疏，改打其 JSON 接口或用浏览器工具。

---

## Project structure · 项目结构

```
openclaw-web-search/
├── SKILL.md                    # agent-facing guide · agent 使用指南
├── scripts/
│   ├── web_search.py           # search → results · 搜索
│   └── web_fetch.py            # fetch URL → Markdown/JSON · 抓取
├── references/
│   └── backends.md             # SearXNG setup + docker-compose · 后端部署
├── tests/
│   ├── run_tests.sh            # 60 assertions · 断言测试套件
│   └── mock_server.py          # deterministic mock server · 确定性 mock
├── .github/workflows/tests.yml # CI
└── LICENSE
```

---

## Tests · 测试

```bash
bash tests/run_tests.sh   # 60 deterministic assertions against a local mock server, no network
```

Covers backends, JSON/Markdown output & envelopes, `-n` bounds, encoding matrix (GBK/meta/UTF-8/latin-1), gzip/deflate, binary rejection, HTTP errors, redirects, timeouts, retry recovery, custom headers, non-ASCII URLs, truncation, `--recent` wiring, search→fetch integration, and concurrency. Runs in CI on every push.

覆盖：后端、JSON/Markdown 输出与信封、`-n` 边界、编码矩阵（GBK/meta/UTF-8/latin-1）、gzip/deflate、二进制拒绝、HTTP 错误、重定向、超时、重试恢复、自定义头、非 ASCII URL、截断、`--recent` 接线、search→fetch 集成、并发。每次 push 自动跑 CI。

See [SKILL.md](SKILL.md) for the agent-facing guide and [references/backends.md](references/backends.md) for SearXNG setup (with a docker-compose snippet).
详见 [SKILL.md](SKILL.md)（agent 指南）与 [references/backends.md](references/backends.md)（SearXNG 部署 + docker-compose）。

---

## License · 许可证

MIT — see [LICENSE](LICENSE).
