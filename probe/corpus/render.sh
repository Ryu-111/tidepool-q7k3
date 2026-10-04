#!/bin/zsh
# render.sh <url> <out.html>: GET one public page in a throwaway headless Chrome profile and save
# the DOM after scripts ran. No cookies, logins, or form submissions; the profile is deleted after.
url=$1; out=$2
prof=$(mktemp -d "${TMPDIR:-/tmp}/jev-render.XXXXXX")
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --user-data-dir="$prof" --no-first-run --no-default-browser-check --disable-extensions \
  --virtual-time-budget=10000 --timeout=30000 \
  --user-agent="jev-autofill-research/0.1 (form structure survey)" \
  --dump-dom "$url" >| "$out" 2>/dev/null &
pid=$!
for i in $(seq 45); do kill -0 $pid 2>/dev/null || break; sleep 1; done
kill $pid 2>/dev/null; wait $pid 2>/dev/null
rm -rf "$prof"
[ -s "$out" ] && echo "rendered $(wc -c < "$out") bytes" || { echo "render failed"; exit 1; }
