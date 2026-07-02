# openclaw-web-search

An [OpenClaw](https://docs.openclaw.ai/) skill that gives agents **web search +
web fetch** using only open-source, no-paid-key backends.

- `web_search.py` — search the web, returns `[{title, url, content}]`.
  - **SearXNG** (recommended) — self-hosted metasearch, no rate limit, offline-capable.
  - **DuckDuckGo** — zero-config fallback via the open-source [`ddgs`](https://github.com/deedy5/ddgs) library.
- `web_fetch.py` — read a URL as clean Markdown (or pretty JSON for data APIs),
  via open-source [`trafilatura`](https://github.com/adbar/trafilatura).

Typical loop: **search** for authoritative links → **fetch** the link to get the
actual content/values (weather, stock quotes, latest data) that search snippets
don't contain.

## Install

Copy the skill into your OpenClaw skills directory:

```bash
cp -r openclaw-web-search ~/.openclaw/skills/web-search
```

Requires [`uv`](https://github.com/astral-sh/uv) (the script auto-installs its
Python deps). Plain `python3 ≥ 3.10` also works — see [SKILL.md](SKILL.md).

## Use

```bash
S=~/.openclaw/skills/web-search/scripts

# search — DuckDuckGo (no setup)
uv run $S/web_search.py "your query" -n 5

# search — SearXNG (set your instance)
export SEARXNG_URL="http://localhost:8080"
uv run $S/web_search.py "your query" --format json

# fetch — read a result's page as Markdown (or JSON for data APIs)
uv run $S/web_fetch.py "https://example.com/article"
```

`web_search` options: `-n/--num` (1–50), `--format md|json`, `--backend auto|searxng|ddg`, `--timeout`, `--retries`.
`web_fetch` options: `--format md|text`, `--max-chars`, `--timeout`, `--retries`, `-H/--header` (repeatable, for Referer/Authorization/Cookie-gated endpoints).
Exit codes (both): `0` ok, `2` usage/unsupported, `3` no results/empty, `4` backend/network error.
Transient failures (429/5xx/network) are retried automatically (default 2, `--retries 0` to disable).

## Tests

```bash
bash tests/run_tests.sh   # 52 deterministic assertions against a local mock server
```

Covers both scripts: backends, JSON/Markdown output, `-n` bounds, GBK decode,
gzip/deflate, binary rejection, HTTP errors, redirects, timeouts, retry recovery,
truncation, search→fetch integration, and concurrent calls. No network required.

See [SKILL.md](SKILL.md) and [references/backends.md](references/backends.md) for
details, SearXNG setup, and a docker-compose snippet.

## License

MIT — see [LICENSE](LICENSE).
