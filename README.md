# openclaw-web-search

[![tests](https://github.com/LeoLin990405/openclaw-web-search/actions/workflows/tests.yml/badge.svg)](https://github.com/LeoLin990405/openclaw-web-search/actions/workflows/tests.yml)

An [OpenClaw](https://docs.openclaw.ai/) skill that gives agents **web search + web fetch** using only open-source, no-paid-key backends.

| Script | Does | Backend (auto-installed via `uv`) |
|---|---|---|
| `scripts/web_search.py` | Search the web → results list | [`ddgs`](https://github.com/deedy5/ddgs) (DuckDuckGo) or self-hosted [SearXNG](https://github.com/searxng/searxng) |
| `scripts/web_fetch.py` | Read a URL → clean Markdown / JSON | [`trafilatura`](https://github.com/adbar/trafilatura) |

Typical loop: **search** for authoritative links → **fetch** the link to get the actual content/values (weather, quotes, latest data) that search snippets don't contain.

## Install

```bash
git clone https://github.com/LeoLin990405/openclaw-web-search ~/.openclaw/skills/web-search
```

Requires [`uv`](https://github.com/astral-sh/uv) (scripts auto-install their Python deps). Plain `python3 ≥ 3.10` also works after `pip install ddgs trafilatura`.

## Usage

```bash
S=~/.openclaw/skills/web-search/scripts

# search (DuckDuckGo, no setup)
uv run $S/web_search.py "your query" -n 5
uv run $S/web_search.py "breaking news" --recent d --region us-en --format json

# search via self-hosted SearXNG (no rate limit, offline-capable)
export SEARXNG_URL="http://localhost:8080"
uv run $S/web_search.py "your query"

# fetch a page as Markdown, a data API as JSON, or with provenance
uv run $S/web_fetch.py "https://example.com/article"
uv run $S/web_fetch.py "https://d1.weather.com.cn/sk_2d/101020100.html" -H "Referer: http://www.weather.com.cn/"
uv run $S/web_fetch.py "https://arxiv.org/abs/1706.03762" --json
```

Both `--format json` (search) and `--json` (fetch) return a provenance envelope with the payload plus metadata (`elapsed_ms`, backend/status/final_url, …).

## Options

**`web_search.py`**

| Option | Default | Meaning |
|---|---|---|
| `-n, --num` | `5` | max results (1–50) |
| `--format md\|json` | `md` | `json` = provenance envelope `{query, backend, count, elapsed_ms, results}` |
| `--backend auto\|searxng\|ddg` | `auto` | `auto` = SearXNG if `SEARXNG_URL` set, else DuckDuckGo |
| `--recent d\|w\|m\|y` | — | only results from the last day/week/month/year |
| `--region` | `wt-wt` | ddg region, e.g. `us-en`, `cn-zh`, `jp-jp` |
| `--safesearch on\|moderate\|off` | `moderate` | ddg safe-search level |
| `--timeout` / `--retries` | `15` / `2` | per-request timeout (s) / retries on 429/5xx/network |

**`web_fetch.py`**

| Option | Default | Meaning |
|---|---|---|
| `--format md\|text` | `md` | HTML → Markdown (keeps links) or plain text |
| `--json` | off | envelope `{url, final_url, status, content_type, kind, chars, truncated, elapsed_ms, content}` |
| `-H, --header` | — | extra request header, repeatable (Referer / Authorization / Cookie) |
| `--max-chars` | `0` | truncate output (`0` = no limit) |
| `--timeout` / `--retries` | `20` / `2` | per-request timeout (s) / retries on 429/5xx/network |

**Environment (SearXNG):** `SEARXNG_URL`, `SEARXNG_LANGUAGE`, `SEARXNG_CATEGORIES`.

## Exit codes (both scripts)

| Code | Meaning |
|---|---|
| `0` | success |
| `2` | usage error / unsupported (binary content, bad header/scheme) |
| `3` | no results / empty content |
| `4` | backend or network error (timeout, unreachable, dependency missing) |

## Behavior notes

- **Encoding:** charset auto-detected (header → `<meta>` → UTF-8 → GBK → latin-1); `gzip`/`deflate` auto-decompressed; non-ASCII URLs percent-encoded (IRI→URI).
- **Binary content** (PDF, images, archives, media) is rejected cleanly (exit 2) — no mojibake. Use a dedicated parser for those.
- **Scope:** `web_fetch` targets article/content pages and data APIs. Homepages and JS-heavy SPAs may extract sparsely — fetch their backing JSON API instead, or use a browser tool.

## Tests

```bash
bash tests/run_tests.sh   # 60 deterministic assertions against a local mock server, no network
```

Covers backends, JSON/Markdown output & envelopes, `-n` bounds, encoding matrix (GBK/meta/UTF-8/latin-1), gzip/deflate, binary rejection, HTTP errors, redirects, timeouts, retry recovery, custom headers, non-ASCII URLs, truncation, `--recent` wiring, search→fetch integration, and concurrency. Runs in CI on every push.

See [SKILL.md](SKILL.md) for the agent-facing guide and [references/backends.md](references/backends.md) for SearXNG setup (with a docker-compose snippet).

## License

MIT — see [LICENSE](LICENSE).
