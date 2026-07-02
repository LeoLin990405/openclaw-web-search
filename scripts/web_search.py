#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["ddgs>=9.0"]
# ///
"""
web_search.py — open-source web search for OpenClaw agents.

Backends (all open-source, no paid API key required):
  * searxng : query a self-hosted SearXNG instance JSON API (recommended,
              set SEARXNG_URL, e.g. http://localhost:8080). No rate limit,
              fully offline-capable, aggregates many engines.
  * ddg     : DuckDuckGo via the open-source `ddgs` package. Zero config,
              no key, good for quick use / when no SearXNG is available.

Backend selection (default `auto`): use SearXNG when SEARXNG_URL is set,
otherwise fall back to DuckDuckGo.

Usage:
  web_search.py "query"                 # 5 results, markdown
  web_search.py "query" -n 8            # 8 results
  web_search.py "query" --format json   # machine-readable JSON
  web_search.py "query" --backend ddg   # force a backend

Exit codes: 0 ok, 2 usage error, 3 no results, 4 backend/network error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# HTTP statuses worth retrying (transient server / rate-limit conditions).
_RETRY_STATUS = {429, 500, 502, 503, 504}


def _err(msg: str, code: int) -> "None":
    print(f"web_search: {msg}", file=sys.stderr)
    sys.exit(code)


def search_searxng(query: str, n: int, timeout: int, retries: int = 2) -> list[dict]:
    base = os.environ.get("SEARXNG_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("SEARXNG_URL not set")
    params = {
        "q": query,
        "format": "json",
        "categories": os.environ.get("SEARXNG_CATEGORIES", "general"),
    }
    lang = os.environ.get("SEARXNG_LANGUAGE")
    if lang:
        params["language"] = lang
    url = f"{base}/search?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "openclaw-web-search/1.0"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
            break
        except urllib.error.HTTPError as e:
            if e.code in _RETRY_STATUS and attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
    out = []
    for r in data.get("results", [])[:n]:
        out.append({
            "title": (r.get("title") or "").strip(),
            "url": r.get("url") or "",
            "content": (r.get("content") or "").strip(),
        })
    return out


def search_ddg(query: str, n: int, timeout: int) -> list[dict]:
    try:
        from ddgs import DDGS  # package renamed: ddgs (was duckduckgo_search)
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # older name fallback
        except ImportError:
            raise RuntimeError(
                "ddgs not installed. Run via `uv run` (auto-installs) or "
                "`pip install ddgs`, or set SEARXNG_URL to use SearXNG."
            )
    out = []
    with DDGS(timeout=timeout) as ddgs:
        for r in ddgs.text(query, max_results=n):
            out.append({
                "title": (r.get("title") or "").strip(),
                "url": r.get("href") or r.get("url") or "",
                "content": (r.get("body") or r.get("content") or "").strip(),
            })
    return out


def run(query: str, n: int, backend: str, timeout: int, retries: int = 2) -> list[dict]:
    have_searxng = bool(os.environ.get("SEARXNG_URL"))
    if backend == "auto":
        backend = "searxng" if have_searxng else "ddg"
    if backend == "searxng":
        return search_searxng(query, n, timeout, retries)
    if backend == "ddg":
        return search_ddg(query, n, timeout)  # ddgs handles its own retries
    raise ValueError(f"unknown backend: {backend}")


def to_markdown(query: str, results: list[dict]) -> str:
    lines = [f"# Web search: {query}", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r['title'] or '(no title)'}**")
        lines.append(f"   {r['url']}")
        if r["content"]:
            lines.append(f"   {r['content']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="web_search.py",
        description="Open-source web search (SearXNG / DuckDuckGo) for OpenClaw.",
    )
    ap.add_argument("query", help="search query")
    ap.add_argument("-n", "--num", type=int, default=5, help="max results (default 5)")
    ap.add_argument("--format", choices=["md", "json"], default="md", help="output format")
    ap.add_argument("--backend", choices=["auto", "searxng", "ddg"], default="auto")
    ap.add_argument("--timeout", type=int, default=15, help="per-request timeout seconds")
    ap.add_argument("--retries", type=int, default=2, help="SearXNG retries on 429/5xx/network (default 2)")
    args = ap.parse_args(argv)

    if not args.query.strip():
        _err("empty query", 2)
    if args.num < 1 or args.num > 50:
        _err("--num must be between 1 and 50", 2)
    if args.retries < 0:
        _err("--retries must be >= 0", 2)

    try:
        results = run(args.query, args.num, args.backend, args.timeout, args.retries)
    except Exception as e:  # noqa: BLE001 - surface any backend/network failure cleanly
        _err(f"{type(e).__name__}: {e}", 4)
        return 4  # unreachable, keeps type checkers happy

    if not results:
        _err("no results", 3)

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(args.query, results), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
