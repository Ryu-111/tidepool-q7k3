#!/bin/zsh
# collect.sh <category> <url>: robots check, GET (static, then headless render), extract,
# follow at most one form link, score, and log. Only value-free JSON is written to raw/.
set -u
cat=$1; url=$2; C=${0:A:h}
H=/private/tmp/claude-501/-Users-ryu-smart-home-agent/ea0f3566-edab-4224-9f1e-9401dc333df9/scratchpad/corpus-html
UA="jev-autofill-research/0.1 (form structure survey)"
mkdir -p $H $C/raw/$cat; log=$C/raw/$cat-log2.tsv
[ -f $log ] || print "status\tscore\tfields\turl\tnote" > $log
note() { print "$1\t${2:-0}\t${3:-0}\t$url\t${4:-}" >> $log; echo "$1 score=${2:-0} $url ${4:-}"; }
host=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.urlparse(sys.argv[1]).hostname or "")' "$url")
[ -z "$host" ] && { note bad-url; exit 0; }
grep -qF "$url" $log 2>/dev/null && [ "$(grep -cF "$url" $log)" -gt 0 ] && { echo "already tried $url"; exit 0; }
upath=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.urlparse(sys.argv[1]).path or "/")' "$url")
if curl -s -m 15 -A "$UA" "https://$host/robots.txt" | python3 -c '
import sys, urllib.robotparser
rp = urllib.robotparser.RobotFileParser(); rp.parse(sys.stdin.read().splitlines())
sys.exit(0 if rp.can_fetch("*", sys.argv[1]) else 1)' "$url"; then :; else note robots; exit 0; fi
slug=$(print -r -- "$host$upath" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-80)
f=$H/$cat-$slug.html
code=$(curl -sL -m 20 -A "$UA" -o $f -w '%{http_code}' "$url")
[ "$code" != 200 ] && { note http-$code; exit 0; }
title=$(python3 -c 'import re,sys;t=re.search(rb"<title[^>]*>(.*?)</title>",open(sys.argv[1],"rb").read(),re.S|re.I);print(t.group(1).decode("utf-8","replace").strip()[:60] if t else "")' $f)
case "$title" in *404*|*見つかりません*|*"Not Found"*|*存在しません*) note not-found 0 0 "$title"; exit 0;; esac
extract() { python3 $C/extract_form.py $1 "$2" $cat >| $3 && python3 $C/profile_score.py $3 | cut -f1; }
out=$C/raw/$cat/$slug.json
s=$(extract $f "$url" $out)
if [ "$s" -lt 4 ]; then
  sleep 2; $C/render.sh "$url" $f.r.html >/dev/null && s=$(extract $f.r.html "$url" $out)
fi
if [ "$s" -lt 4 ]; then
  # One hop: the first link on the page that looks like the actual form (same site or a form service).
  next=$(python3 - "$f" "$url" <<'PY'
import re, sys, urllib.parse
html = open(sys.argv[1], "rb").read().decode("utf-8", "replace")
base = urllib.parse.urlparse(sys.argv[2])
services = re.compile(r"kintoneapp|logoform|graffer|e-tumo|harp\.lg|form\.run|formrun|docs\.google\.com/forms|"
                      r"forms\.gle|typeform|questant|formzu|form-mailer|cuenote|spiral|shinsei|e-shinsei|"
                      r"apply|mousikomi|moushikomi|entry|form", re.I)
best = (0, None)
for m in re.finditer(r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
    href, text = m.group(1).replace("&amp;", "&"), re.sub(r"<[^>]+>|\s+", "", m.group(2))
    link = urllib.parse.urljoin(sys.argv[2], href)
    if not link.startswith("http") or link.rstrip("/") == sys.argv[2].rstrip("/"):
        continue
    score = 0
    if re.search(r"申込フォーム|申し込みフォーム|申請フォーム|入力フォーム|応募フォーム|予約フォーム|請求フォーム", text): score += 3
    elif re.search(r"申込|申し込|申請|予約|請求|応募|登録", text) and len(text) <= 30: score += 1
    if services.search(link): score += 2
    if urllib.parse.urlparse(link).hostname != base.hostname and services.search(link): score += 1
    if score > best[0]: best = (score, link)
if best[0] >= 2: print(best[1])
PY
)
  if [ -n "$next" ]; then
    sleep 3; nf=$f.next.html
    ncode=$(curl -sL -m 20 -A "$UA" -o $nf -w '%{http_code}' "$next")
    if [ "$ncode" = 200 ]; then
      s=$(extract $nf "$next" $out)
      [ "$s" -lt 4 ] && { sleep 2; $C/render.sh "$next" $nf.r.html >/dev/null && s=$(extract $nf.r.html "$next" $out); }
    fi
  fi
fi
fields=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["field_count"])' $out 2>/dev/null || echo 0)
if [ "$s" -ge 4 ]; then note ok $s $fields "$title"; else rm -f $out; note low $s $fields "$title"; fi
