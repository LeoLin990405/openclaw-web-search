#!/usr/bin/env bash
# Full-functionality test suite for the OpenClaw web-search skill.
# Deterministic: all assertions run against a local mock server (no live net).
# Usage: bash tests/run_tests.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
PORT=8977
BASE="http://127.0.0.1:$PORT"
SEARCH="uv run $ROOT/scripts/web_search.py"
FETCH="uv run $ROOT/scripts/web_fetch.py"

PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m %s\n' "$1"; }
no(){ FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m %s\n     %s\n' "$1" "$2"; }

# run CMD... ; sets $OUT (stdout+stderr) and $EC (exit code)
run(){ OUT="$("$@" 2>&1)"; EC=$?; }

assert_exit(){ [ "$EC" = "$1" ] && ok "$2 (exit $1)" || no "$2" "expected exit $1, got $EC :: ${OUT:0:120}"; }
assert_has(){ case "$OUT" in *"$1"*) ok "$2";; *) no "$2" "missing '$1' in :: ${OUT:0:160}";; esac; }
assert_exit_has(){ if [ "$EC" = "$1" ] && case "$OUT" in *"$2"*) true;; *) false;; esac; then ok "$3"; else no "$3" "want exit $1 & '$2'; got exit $EC :: ${OUT:0:140}"; fi; }

echo "== starting mock server on :$PORT =="
python3 "$HERE/mock_server.py" $PORT & MOCK=$!
trap 'kill $MOCK 2>/dev/null' EXIT
sleep 1

echo; echo "### web_search ###"
SEARXNG_URL="$BASE" run $SEARCH "hello"          ; assert_exit 0 "searxng auto md"
                                                           assert_has "Result 1" "searxng returns results"
SEARXNG_URL="$BASE" run $SEARCH "hi" -n 2 --format json
  CNT=$(echo "$OUT" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['results']))" 2>/dev/null)
  [ "$CNT" = "2" ] && ok "json -n respected (2)" || no "json -n" "count=$CNT :: ${OUT:0:120}"
  echo "$OUT" | python3 -c "import json,sys;d=json.load(sys.stdin);assert {'query','backend','count','elapsed_ms','results'}<=set(d) and all({'title','url','content'}<=set(x) for x in d['results'])" 2>/dev/null && ok "json schema" || no "json schema" "${OUT:0:120}"
run $SEARCH ""                                           ; assert_exit 2 "empty query -> usage"
run $SEARCH "x" -n 0                                     ; assert_exit 2 "-n 0 -> usage"
run $SEARCH "x" -n 51                                    ; assert_exit 2 "-n 51 -> usage"
run $SEARCH "x" --backend searxng                        ; assert_exit_has 4 "SEARXNG_URL" "forced searxng w/o URL -> err"
SEARXNG_URL="http://127.0.0.1:9" run $SEARCH "x" --backend searxng ; assert_exit 4 "searxng dead host -> backend err"

echo; echo "### web_fetch: content types ###"
run $FETCH "$BASE/html"                                  ; assert_exit 0 "html fetch"
                                                           assert_has "quick brown fox" "html -> article text"
run $FETCH "$BASE/html"                                  ; assert_has "useful link" "md keeps links"
run $FETCH "$BASE/html" --format text                    ; assert_exit 0 "html text mode"
run $FETCH "$BASE/json"                                  ; assert_exit_has 0 '"list"' "json pretty-printed"
run $FETCH "$BASE/html-gbk"                              ; assert_exit_has 0 "快速的棕色狐狸" "GBK decoded"
run $FETCH "$BASE/gzip"                                  ; assert_exit_has 0 '"gz"' "gzip decompressed"
run $FETCH "$BASE/deflate"                               ; assert_exit_has 0 "deflated plain text" "deflate decompressed"

echo; echo "### web_fetch: binary rejection ###"
run $FETCH "$BASE/pdf"                                   ; assert_exit_has 2 "binary" "pdf -> clean err"
run $FETCH "$BASE/png"                                   ; assert_exit_has 2 "binary" "png -> clean err"

echo; echo "### web_fetch: http/network ###"
run $FETCH "$BASE/status/404"                            ; assert_exit 4 "404 -> err"
run $FETCH "$BASE/status/403"                            ; assert_exit 4 "403 -> err"
run $FETCH "$BASE/redirect"                              ; assert_exit_has 0 "quick brown fox" "302 followed"
run $FETCH "$BASE/slow" --timeout 2 --retries 0         ; assert_exit 4 "timeout -> err (no retry)"
run $FETCH "ftp://nope"                                  ; assert_exit 2 "bad scheme -> usage"
run $FETCH "$BASE/empty"                                 ; assert_exit 3 "empty body -> no content"

echo; echo "### web_fetch: custom headers ###"
run $FETCH "$BASE/needs-referer"                        ; assert_exit 4 "referer-gated w/o header -> 403"
run $FETCH "$BASE/needs-referer" -H "Referer: http://x/" ; assert_exit_has 0 "quick brown fox" "referer header unlocks"
run $FETCH "$BASE/html" -H "badheader"                  ; assert_exit 2 "malformed header -> usage"

echo; echo "### web_fetch: retry on transient 5xx ###"
run $FETCH "$BASE/flaky" --retries 2                     ; assert_exit_has 0 "quick brown fox" "flaky 503x2 recovered via retry"
run $FETCH "$BASE/status/503" --retries 0               ; assert_exit 4 "503 with --retries 0 -> fails fast"

echo; echo "### web_fetch: options ###"
run $FETCH "$BASE/big" --max-chars 500
  LEN=${#OUT}
  [ "$LEN" -le 560 ] && ok "max-chars truncates ($LEN<=560)" || no "max-chars" "len=$LEN"
                                                           assert_has "truncated at 500" "truncation marker"

echo; echo "### integration: search -> fetch ###"
SEARXNG_URL="$BASE" run $SEARCH "x" -n 1 --format json
  U=$(echo "$OUT" | python3 -c "import json,sys;print(json.load(sys.stdin)['results'][0]['url'])" 2>/dev/null)
  [ -n "$U" ] && ok "extracted url from search ($U)" || no "search->url" "no url"

echo; echo "### concurrency: 5 parallel fetches ###"
pids=""; for i in 1 2 3 4 5; do ($FETCH "$BASE/html" >/dev/null 2>&1) & pids="$pids $!"; done
cfail=0; for pid in $pids; do wait $pid || cfail=$((cfail+1)); done
[ "$cfail" = 0 ] && ok "5 parallel fetches all ok" || no "concurrency" "$cfail failed"

echo; echo "### web_search: extended ###"
SEARXNG_URL="$BASE" run $SEARCH "__empty__"              ; assert_exit 3 "searxng empty results -> exit 3"
SEARXNG_URL="$BASE" run $SEARCH "__bad__"                ; assert_exit 4 "searxng invalid JSON -> exit 4"
SEARXNG_URL="$BASE" run $SEARCH "__many__" -n 10 --format json
  CNT=$(echo "$OUT" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['results']))" 2>/dev/null)
  [ "$CNT" = "10" ] && ok "n caps results (10 of 30)" || no "n cap" "count=$CNT"
SEARXNG_URL="$BASE" run $SEARCH "__many__" -n 50 --format json
  CNT=$(echo "$OUT" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['results']))" 2>/dev/null)
  [ "$CNT" = "30" ] && ok "n>available returns all (30)" || no "n>avail" "count=$CNT"
SEARXNG_URL="$BASE" run $SEARCH "__flaky__" --retries 2  ; assert_exit_has 0 "Result 1" "searxng 503x2 recovered via retry"
SEARXNG_URL="$BASE" run $SEARCH 'a b & c # 中文' --format json
                                                           assert_has 'q=a b & c # 中文' "query special chars url-encoded round-trip"
SEARXNG_URL="$BASE" run $SEARCH "news" --recent w --format json
                                                           assert_has 'tr=week' "--recent w -> searxng time_range=week"
SEARXNG_URL="$BASE" run $SEARCH "news" --format json      ; assert_has 'q=news;tr="' "no --recent -> empty time_range"
run $SEARCH "x" --recent bad                              ; assert_exit 2 "invalid --recent -> usage"
SEARXNG_URL="$BASE" run $SEARCH "hello" -n 3 --format json
  echo "$OUT" | python3 -c "import json,sys;d=json.load(sys.stdin);assert d['backend']=='searxng' and isinstance(d['elapsed_ms'],int) and d['count']==len(d['results'])==3 and d['query']=='hello'" 2>/dev/null \
    && ok "search json provenance (backend/elapsed/count/query)" || no "search provenance" "${OUT:0:160}"

echo; echo "### web_fetch: encoding matrix ###"
run $FETCH "$BASE/meta-charset"                          ; assert_exit_has 0 "元数据编码测试" "GBK via <meta> (no header charset)"
run $FETCH "$BASE/nocharset-utf8"                        ; assert_exit_has 0 "没有任何字符集声明的中文正文" "utf-8 with no charset declared"
run $FETCH "$BASE/latin1"                                ; assert_exit_has 0 "café résumé" "latin-1 header charset"
run $FETCH "$BASE/jsontext"                              ; assert_exit_has 0 '"served"' "JSON served as text/plain -> pretty JSON"
run $FETCH "$BASE/unicode?name=東京&x=مصر"                ; assert_exit_has 0 "quick brown fox" "non-ASCII URL percent-encoded (IRI->URI)"
run $FETCH "$BASE/unicode?pre=%E5%B7%B2%E7%Bc%96%E7%A0%81" ; assert_exit 0 "pre-encoded %XX not double-encoded"

echo; echo "### web_fetch: 204 & headers ###"
run $FETCH "$BASE/status/204"                            ; assert_exit 3 "204 No Content -> empty"
run $FETCH "$BASE/echo-headers"                          ; assert_has "openclaw-web-fetch" "default User-Agent sent"
run $FETCH "$BASE/echo-headers" -H "X-Test: a: b"        ; assert_has '"a: b"' "header value keeps colons"
run $FETCH "$BASE/echo-headers" -H "X-Dup: first" -H "X-Dup: second" ; assert_has "second" "duplicate header last wins"

echo; echo "### web_fetch: --json envelope ###"
run $FETCH "$BASE/html" --json
  echo "$OUT" | python3 -c "import json,sys;d=json.load(sys.stdin);assert d['status']==200 and d['kind']=='markdown' and 'quick brown fox' in d['content'] and isinstance(d['elapsed_ms'],int) and {'url','final_url','content_type','chars','truncated','elapsed_ms'}<=set(d)" 2>/dev/null \
    && ok "json envelope shape+content" || no "json envelope" "${OUT:0:160}"
run $FETCH "$BASE/redirect" --json
  FU=$(echo "$OUT" | python3 -c "import json,sys;print(json.load(sys.stdin)['final_url'])" 2>/dev/null)
  case "$FU" in */html) ok "json final_url resolved through redirect ($FU)";; *) no "json final_url" "got $FU";; esac
run $FETCH "$BASE/big" --json --max-chars 300
  echo "$OUT" | python3 -c "import json,sys;d=json.load(sys.stdin);assert d['truncated'] is True and d['chars']==300" 2>/dev/null \
    && ok "json truncated flag + chars" || no "json truncated" "${OUT:0:160}"
run $FETCH "$BASE/json" --json
  echo "$OUT" | python3 -c "import json,sys;d=json.load(sys.stdin);assert d['kind']=='json'" 2>/dev/null \
    && ok "json envelope kind=json for API" || no "json kind" "${OUT:0:160}"

echo; echo "### web_fetch: max-chars boundaries ###"
run $FETCH "$BASE/big" --max-chars 0
  [ "${#OUT}" -gt 1000 ] && ok "max-chars 0 = no limit (${#OUT} chars)" || no "max-chars 0" "len=${#OUT}"
run $FETCH "$BASE/html" --max-chars 100000               ; assert_exit_has 0 "quick brown fox" "max-chars > content = untouched"

echo; echo "========================================"
echo "  PASS=$PASS  FAIL=$FAIL"
echo "========================================"
[ "$FAIL" = 0 ]
