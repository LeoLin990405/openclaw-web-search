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
  CNT=$(echo "$OUT" | python3 -c "import json,sys;print(len(json.load(sys.stdin)))" 2>/dev/null)
  [ "$CNT" = "2" ] && ok "json -n respected (2)" || no "json -n" "count=$CNT :: ${OUT:0:120}"
  echo "$OUT" | python3 -c "import json,sys;d=json.load(sys.stdin);assert all({'title','url','content'}<=set(x) for x in d)" 2>/dev/null && ok "json schema" || no "json schema" "${OUT:0:120}"
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
  U=$(echo "$OUT" | python3 -c "import json,sys;print(json.load(sys.stdin)[0]['url'])" 2>/dev/null)
  [ -n "$U" ] && ok "extracted url from search ($U)" || no "search->url" "no url"

echo; echo "### concurrency: 5 parallel fetches ###"
pids=""; for i in 1 2 3 4 5; do ($FETCH "$BASE/html" >/dev/null 2>&1) & pids="$pids $!"; done
cfail=0; for pid in $pids; do wait $pid || cfail=$((cfail+1)); done
[ "$cfail" = 0 ] && ok "5 parallel fetches all ok" || no "concurrency" "$cfail failed"

echo; echo "========================================"
echo "  PASS=$PASS  FAIL=$FAIL"
echo "========================================"
[ "$FAIL" = 0 ]
