#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["trafilatura>=1.8"]
# ///
"""
web_fetch.py — fetch a URL and return clean, LLM-ready content.

Open-source, no key. Pairs with web_search.py: search returns links,
fetch reads a link's content.

Behavior:
  * JSON responses  -> pretty-printed JSON (handy for data APIs).
  * HTML pages      -> main-content Markdown via trafilatura (strips nav,
                       ads, boilerplate). Falls back to raw text if
                       extraction yields nothing.
  * other text      -> returned as-is (charset auto-detected).

Usage:
  web_fetch.py https://example.com/article
  web_fetch.py https://api.example.com/data.json
  web_fetch.py URL --format text        # plain text instead of markdown
  web_fetch.py URL --max-chars 8000      # truncate long output

Exit codes: 0 ok, 2 usage error, 3 empty content, 4 fetch/network error.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request


def _err(msg: str, code: int) -> None:
    print(f"web_fetch: {msg}", file=sys.stderr)
    sys.exit(code)


def fetch(url: str, timeout: int) -> tuple[bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; openclaw-web-fetch/1.0)",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ctype = resp.headers.get("Content-Type", "")
        return resp.read(), ctype


def decode(raw: bytes, ctype: str) -> str:
    # honor charset in header, else try utf-8 then gbk (common on CN sites)
    charset = ""
    if "charset=" in ctype.lower():
        charset = ctype.lower().split("charset=", 1)[1].split(";")[0].strip()
    for enc in [charset, "utf-8", "gbk", "latin-1"]:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def to_output(url: str, raw: bytes, ctype: str, fmt: str) -> str:
    lc = ctype.lower()
    text = decode(raw, ctype)

    if "json" in lc or (text.lstrip()[:1] in "{[" and "html" not in lc):
        try:
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass  # not valid JSON, fall through

    if "html" in lc or "<html" in text[:2000].lower():
        try:
            import trafilatura
        except ImportError:
            _err(
                "trafilatura not installed. Run via `uv run` (auto-installs) "
                "or `pip install trafilatura`.",
                4,
            )
        output_fmt = "txt" if fmt == "text" else "markdown"
        extracted = trafilatura.extract(
            text, url=url, output_format=output_fmt,
            include_links=(fmt != "text"), favor_precision=True,
        )
        if extracted and extracted.strip():
            return extracted.strip()
        # extraction empty -> fall back to raw text below

    return text.strip()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="web_fetch.py",
        description="Fetch a URL and return clean Markdown/JSON/text for agents.",
    )
    ap.add_argument("url", help="URL to fetch (http/https)")
    ap.add_argument("--format", choices=["md", "text"], default="md")
    ap.add_argument("--max-chars", type=int, default=0, help="truncate output (0 = no limit)")
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args(argv)

    if not args.url.lower().startswith(("http://", "https://")):
        _err("url must start with http:// or https://", 2)

    try:
        raw, ctype = fetch(args.url, args.timeout)
    except Exception as e:  # noqa: BLE001 - surface network/fetch failures cleanly
        _err(f"{type(e).__name__}: {e}", 4)
        return 4  # unreachable

    out = to_output(args.url, raw, ctype, args.format)
    if not out:
        _err("empty content", 3)
    if args.max_chars and len(out) > args.max_chars:
        out = out[: args.max_chars] + f"\n\n[... truncated at {args.max_chars} chars]"
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
