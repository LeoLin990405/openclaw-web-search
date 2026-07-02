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
import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

# URL-legal ASCII chars kept as-is; '%' kept so existing %XX escapes aren't
# double-encoded. Everything else (non-ASCII: CJK/Arabic/Cyrillic paths) is
# percent-encoded so urllib can issue the request (IRI -> URI).
_URL_SAFE = ":/?#[]@!$&'()*+,;=-._~%"

# HTTP statuses worth retrying (transient server / rate-limit conditions).
_RETRY_STATUS = {429, 500, 502, 503, 504}

# Content-Type prefixes we treat as text-ish; anything else (pdf, image,
# octet-stream, zip, audio, video, ...) is rejected as binary.
_TEXT_HINTS = (
    "text/", "json", "xml", "html", "javascript", "ecmascript",
    "x-www-form-urlencoded", "csv", "yaml",
)


def _err(msg: str, code: int) -> None:
    print(f"web_fetch: {msg}", file=sys.stderr)
    sys.exit(code)


def _decompress(data: bytes, encoding: str) -> bytes:
    enc = (encoding or "").lower()
    if "gzip" in enc:
        return gzip.decompress(data)
    if "deflate" in enc:
        try:
            return zlib.decompress(data)
        except zlib.error:
            return zlib.decompress(data, -zlib.MAX_WBITS)  # raw deflate
    return data


def fetch(url: str, timeout: int, retries: int = 2, headers: "dict | None" = None) -> "tuple[bytes, str, str, int]":
    hdrs = {
        "User-Agent": "Mozilla/5.0 (compatible; openclaw-web-fetch/1.0)",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
    }
    hdrs.update(headers or {})  # caller headers win (e.g. Referer, Authorization)
    req = urllib.request.Request(urllib.parse.quote(url, safe=_URL_SAFE), headers=hdrs)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ctype = resp.headers.get("Content-Type", "")
                data = _decompress(resp.read(), resp.headers.get("Content-Encoding", ""))
                final_url = resp.geturl()
                status = resp.status
            return data, ctype, final_url, status
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
    raise RuntimeError("unreachable")  # pragma: no cover


def _is_binary(ctype: str, raw: bytes) -> bool:
    lc = ctype.lower()
    if lc and any(h in lc for h in _TEXT_HINTS):
        return False
    if lc and ("application/" in lc or lc.startswith(("image/", "audio/", "video/", "font/"))):
        return True
    # no/ambiguous content-type: sniff for NUL bytes in the first chunk
    return b"\x00" in raw[:1024]


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


def to_output(url: str, raw: bytes, ctype: str, fmt: str) -> "tuple[str, str]":
    """Return (content, kind) where kind is 'json' | 'markdown' | 'text'."""
    lc = ctype.lower()
    text = decode(raw, ctype)

    if "json" in lc or (text.lstrip()[:1] in "{[" and "html" not in lc):
        try:
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2), "json"
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
        if not _meaningful(extracted):
            # main-content extraction failed (e.g. homepage/index) -> grab all text
            extracted = trafilatura.html2txt(text)
        if _meaningful(extracted):
            return extracted.strip(), ("text" if fmt == "text" else "markdown")
        # still nothing usable -> fall through to raw below

    return text.strip(), "text"


def _meaningful(s: "str | None") -> bool:
    """True if s has real content (not just whitespace / list bullets)."""
    if not s:
        return False
    import re
    return len(re.sub(r"[\s\-|*#>_.]", "", s)) >= 30


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="web_fetch.py",
        description="Fetch a URL and return clean Markdown/JSON/text for agents.",
    )
    ap.add_argument("url", help="URL to fetch (http/https)")
    ap.add_argument("--format", choices=["md", "text"], default="md")
    ap.add_argument("--max-chars", type=int, default=0, help="truncate output (0 = no limit)")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--retries", type=int, default=2, help="retries on 429/5xx/network (default 2)")
    ap.add_argument(
        "-H", "--header", action="append", default=[], metavar="'Name: Value'",
        help="extra request header (repeatable), e.g. -H 'Referer: https://site/' -H 'Authorization: Bearer X'",
    )
    ap.add_argument(
        "--json", action="store_true",
        help="emit a JSON envelope with provenance: {url, final_url, status, content_type, kind, chars, truncated, content}",
    )
    args = ap.parse_args(argv)

    if not args.url.lower().startswith(("http://", "https://")):
        _err("url must start with http:// or https://", 2)
    if args.retries < 0:
        _err("--retries must be >= 0", 2)

    headers = {}
    for h in args.header:
        if ":" not in h:
            _err(f"bad header (need 'Name: Value'): {h}", 2)
        k, v = h.split(":", 1)
        headers[k.strip()] = v.strip()

    try:
        raw, ctype, final_url, status = fetch(args.url, args.timeout, args.retries, headers)
    except Exception as e:  # noqa: BLE001 - surface network/fetch failures cleanly
        _err(f"{type(e).__name__}: {e}", 4)
        return 4  # unreachable

    if _is_binary(ctype, raw):
        _err(
            f"binary content ({ctype or 'unknown type'}); web_fetch returns "
            "text/HTML/JSON only, not PDFs/images/archives",
            2,
        )

    out, kind = to_output(args.url, raw, ctype, args.format)
    if not out:
        _err("empty content", 3)
    truncated = bool(args.max_chars and len(out) > args.max_chars)
    if truncated:
        out = out[: args.max_chars]

    if args.json:
        print(json.dumps({
            "url": args.url,
            "final_url": final_url,
            "status": status,
            "content_type": ctype,
            "kind": kind,
            "chars": len(out),
            "truncated": truncated,
            "content": out,
        }, ensure_ascii=False, indent=2))
    else:
        if truncated:
            out += f"\n\n[... truncated at {args.max_chars} chars]"
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
