#!/usr/bin/env python3
"""Deterministic mock server for the web-search skill test suite.

Routes:
  /searxng?q=...       -> SearXNG-style JSON (respects nothing, fixed 3 results)
  /json                -> a small JSON document
  /html                -> an article-like HTML page (UTF-8)
  /html-gbk            -> HTML declared + encoded as GBK (Chinese)
  /gzip                -> gzip-compressed JSON body (Content-Encoding: gzip)
  /deflate             -> deflate-compressed text
  /pdf                 -> application/pdf binary
  /png                 -> image/png binary
  /status/<code>       -> empty body with that HTTP status
  /redirect            -> 302 -> /html
  /slow                -> sleeps 5s then 200
  /big                 -> a large HTML page (~50k chars of real text)
  /empty               -> 200 with empty body
"""
import gzip
import json
import sys
import time
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

SEARX = {"results": [
    {"title": f"Result {i}", "url": f"https://ex.test/{i}", "content": f"snippet number {i}"}
    for i in range(1, 6)
]}
ARTICLE = (
    "<!doctype html><html><head><title>Test Article</title></head><body>"
    "<nav>home about contact</nav>"
    "<article><h1>The Quick Brown Fox</h1>"
    "<p>The quick brown fox jumps over the lazy dog. This paragraph has enough "
    "real sentences to be treated as genuine main content by the extractor, so "
    "that content extraction succeeds and returns clean readable text.</p>"
    "<p>A second paragraph continues the article with more meaningful prose and "
    "a <a href='https://ex.test/link'>useful link</a> for good measure.</p>"
    "</article><footer>copyright</footer></body></html>"
)
BIG = "<!doctype html><html><body><article><h1>Big</h1>" + \
      ("<p>Sentence with several real words repeated for bulk content. </p>" * 1200) + \
      "</article></body></html>"

# /flaky: 503 for the first 2 hits, then 200 — exercises retry logic.
_flaky = {"hits": 0}
# /search?q=__flaky__ : SearXNG that 503s twice then succeeds (search-side retry).
_search_flaky = {"hits": 0}


def _searx_results(n):
    return {"results": [
        {"title": f"Result {i}", "url": f"https://ex.test/{i}", "content": f"snippet number {i}"}
        for i in range(1, n + 1)
    ]}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="text/html; charset=utf-8", extra=None):
        self.send_response(code)
        if body:
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body and self.command == "GET":
            self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        p = parsed.path
        if p == "/search":  # SearXNG convention: {base}/search — branch on q sentinel
            q = (parse_qs(parsed.query).get("q") or [""])[0]
            if "__empty__" in q:
                self._send(200, json.dumps({"results": []}).encode(), "application/json")
            elif "__bad__" in q:
                self._send(200, b"<<not json at all>>", "application/json")
            elif "__many__" in q:
                self._send(200, json.dumps(_searx_results(30)).encode(), "application/json")
            elif "__flaky__" in q:
                _search_flaky["hits"] += 1
                if _search_flaky["hits"] <= 2:
                    self._send(503)
                else:
                    self._send(200, json.dumps(_searx_results(5)).encode(), "application/json")
            else:
                qs = parse_qs(parsed.query)
                tr = (qs.get("time_range") or [""])[0]
                r = _searx_results(5)
                r["results"][0]["content"] = f"q={q};tr={tr}"  # echo for encoding/time checks
                self._send(200, json.dumps(r).encode(), "application/json")
        elif p == "/json":
            self._send(200, json.dumps({"a": 1, "list": [1, 2, 3]}).encode(), "application/json")
        elif p == "/html":
            self._send(200, ARTICLE.encode("utf-8"))
        elif p == "/html-gbk":
            html = ARTICLE.replace("Test Article", "测试文章").replace(
                "The Quick Brown Fox", "快速的棕色狐狸").replace(
                "charset=utf-8", "charset=gbk")
            body = html.encode("gbk", "replace")
            self._send(200, body, "text/html; charset=gbk")
        elif p == "/gzip":
            self._send(200, gzip.compress(json.dumps({"gz": True}).encode()),
                       "application/json", {"Content-Encoding": "gzip"})
        elif p == "/deflate":
            self._send(200, zlib.compress(b"deflated plain text body ok"),
                       "text/plain", {"Content-Encoding": "deflate"})
        elif p == "/pdf":
            self._send(200, b"%PDF-1.4\n%\xc3\xa4\n1 0 obj\nbinary", "application/pdf")
        elif p == "/png":
            self._send(200, b"\x89PNG\r\n\x1a\n\x00\x00binary", "image/png")
        elif p.startswith("/status/") and p.rsplit("/", 1)[1].isdigit():
            self._send(int(p.rsplit("/", 1)[1]))
        elif p == "/redirect":
            self._send(302, extra={"Location": "/html"})
        elif p == "/slow":
            time.sleep(5)
            self._send(200, b"late", "text/plain")
        elif p == "/big":
            self._send(200, BIG.encode("utf-8"))
        elif p == "/empty":
            self._send(200)
        elif p == "/status/204":
            self._send(204)
        elif p == "/meta-charset":
            # header says no charset; charset only in <meta> — body is GBK
            html = ("<!doctype html><html><head><meta charset='gbk'>"
                    "<title>元</title></head><body><article><h1>元数据编码测试</h1>"
                    "<p>这是一段足够长的中文正文用来让抽取器认定为主要内容并成功返回可读文本内容。</p>"
                    "</article></body></html>")
            self._send(200, html.encode("gbk", "replace"), "text/html")  # no charset in header
        elif p == "/nocharset-utf8":
            # no charset anywhere; utf-8 Chinese body should decode via fallback
            html = ("<!doctype html><html><body><article><h1>无声明编码</h1>"
                    "<p>这是一段没有任何字符集声明的中文正文，内容足够长以便被抽取器"
                    "识别为主要正文并成功返回可读的中文文本供断言校验使用。</p>"
                    "</article></body></html>")
            self._send(200, html.encode("utf-8"), "text/html")
        elif p == "/latin1":
            self._send(200, "café résumé naïve".encode("latin-1"),
                       "text/plain; charset=iso-8859-1")
        elif p == "/jsontext":
            # JSON body served as text/plain -> should still be detected & pretty-printed
            self._send(200, b'{"served":"as text","n":7}', "text/plain")
        elif p == "/echo-headers":
            self._send(200, json.dumps(dict(self.headers)).encode(), "application/json")
        elif p == "/unicode":
            # reached only if a non-ASCII URL was percent-encoded correctly
            self._send(200, ARTICLE.encode("utf-8"))
        elif p == "/needs-referer":
            if self.headers.get("Referer"):
                self._send(200, ARTICLE.encode("utf-8"))
            else:
                self._send(403)
        elif p == "/flaky":
            _flaky["hits"] += 1
            if _flaky["hits"] <= 2:
                self._send(503)
            else:
                self._send(200, ARTICLE.encode("utf-8"))
        else:
            self._send(404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8977
    HTTPServer(("127.0.0.1", port), H).serve_forever()
