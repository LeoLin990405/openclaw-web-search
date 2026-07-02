# web-search backends

All backends are open-source and require no paid API key.

## Backend selection

`web_search.py --backend {auto,searxng,ddg}` (default `auto`):

- `auto` → `searxng` if `SEARXNG_URL` is set, else `ddg`.
- `searxng` → force SearXNG (errors if `SEARXNG_URL` unset).
- `ddg` → force DuckDuckGo.

## SearXNG (recommended for production)

Self-hosted metasearch engine — MIT, no rate limits, no key, aggregates
Google/Bing/DuckDuckGo/etc. Repo: https://github.com/searxng/searxng

Enable in this skill:

```bash
export SEARXNG_URL="http://localhost:8080"
export SEARXNG_LANGUAGE="zh-CN"   # optional
export SEARXNG_CATEGORIES="general"  # optional (default general)
```

The script calls `GET {SEARXNG_URL}/search?q=...&format=json` and reads
`results[].{title,url,content}`. **You must enable the JSON output format
in the instance's `settings.yml`:**

```yaml
search:
  formats:
    - html
    - json
```

### 5-minute docker-compose

```yaml
# docker-compose.yml
services:
  searxng:
    image: searxng/searxng:latest
    ports:
      - "8080:8080"
    volumes:
      - ./searxng:/etc/searxng:rw
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080/
    restart: unless-stopped
```

```bash
mkdir -p searxng
# create searxng/settings.yml with the `formats: [html, json]` block above
docker compose up -d
curl "http://localhost:8080/search?q=test&format=json" | head
```

## DuckDuckGo (`ddg`)

Uses the open-source `ddgs` package (https://github.com/deedy5/ddgs — the
renamed `duckduckgo_search`). No key, no config. `uv run` auto-installs it
via the script's inline dependency metadata (PEP 723). For plain `python3`,
`pip install ddgs` first.

Trade-offs: subject to DuckDuckGo's own rate limiting under heavy use — for
a busy always-on agent prefer self-hosted SearXNG.

## Output schema

Both backends normalize to:

```json
[
  {"title": "...", "url": "https://...", "content": "snippet ..."}
]
```

`content` may be empty for some results; `title`/`url` are always present.
