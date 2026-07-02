# openclaw-web-search

An [OpenClaw](https://docs.openclaw.ai/) skill that gives agents **web search**
using only open-source, no-paid-key backends.

- **SearXNG** (recommended) — self-hosted metasearch, no rate limit, offline-capable.
- **DuckDuckGo** — zero-config fallback via the open-source [`ddgs`](https://github.com/deedy5/ddgs) library.

## Install

Copy the skill into your OpenClaw skills directory:

```bash
cp -r openclaw-web-search ~/.openclaw/skills/web-search
```

Requires [`uv`](https://github.com/astral-sh/uv) (the script auto-installs its
Python deps). Plain `python3 ≥ 3.10` also works — see [SKILL.md](SKILL.md).

## Use

```bash
# DuckDuckGo (no setup)
uv run ~/.openclaw/skills/web-search/scripts/web_search.py "your query" -n 5

# SearXNG (set your instance)
export SEARXNG_URL="http://localhost:8080"
uv run ~/.openclaw/skills/web-search/scripts/web_search.py "your query" --format json
```

Options: `-n/--num` (1–50), `--format md|json`, `--backend auto|searxng|ddg`,
`--timeout`. Exit codes: `0` ok, `2` usage, `3` no results, `4` backend error.

See [SKILL.md](SKILL.md) and [references/backends.md](references/backends.md) for
details, SearXNG setup, and a docker-compose snippet.

## License

MIT — see [LICENSE](LICENSE).
