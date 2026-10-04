# 実フォーム構造コーパス（引き継ぎ用）

作成: 2026-09-29（Claude）。公開されている日本語の申込・会員登録フォームから、**値を含まない構造だけ**を集めた試験用の資料。合成ページ（`fixture/patterns/`）では測れない、実際のフォームの揺れを測るために作った。

## 何が入っているか

| パス | 内容 |
|---|---|
| `raw/<分野>/*.json` | 1ページ1ファイル。欄ごとに tag、type、name、id、placeholder、autocomplete、maxlength、required、label（`<label>` の文字列）、near（直前の文字列3つ）、legend、select の選択肢の文言を持つ。**入力値、hidden 欄、送信先のパスは保存していない。** |
| `raw/<分野>-log.md` | 1巡目の試行記録（Haiku が手で書いたもの。精度は低い） |
| `raw/<分野>-log2.tsv` | 2巡目の試行記録（`collect.sh` が自動で書いたもの。`status score fields url note`） |
| `eval/usable.txt` | 使えると判定したページ 98件（プロフィール系の欄が4つ以上。URL で重複を除いたもの） |
| `eval/all-before.tsv` | 98ページを現行の端末内ルールで判定した結果（1欄1行: `page#form idx kind shape evidence`） |
| `index.tsv` | 1巡目の分の一覧（スコア順） |
| `excluded/` | 取り違えで除外したファイル（ec の担当が finance の HTML を偽の URL で抽出したもの） |
| `raw/FINAL_REPORT.md`、`gov-summary.txt`、`travel-analysis.txt` | サブエージェントが指示なしに書いたメモ。**未検証。数字は信用しないこと。** |

集めた数（2026-09-29 00:50 JST 時点）: 使えるページ 98 / 95サイト。フォーム 156、欄 2006。

| 分野 | ページ数 | 対象 |
|---|---|---|
| ec | 26 | 通販の会員登録、お届け先、カタログ・サンプル請求 |
| finance | 17 | 保険の資料請求・見積、カード・銀行の資料請求 |
| misc | 17 | 不動産、試乗予約、リフォーム見積、クリニック、式場 |
| jobsedu | 16 | 採用応募、専門学校・大学の資料請求やオープンキャンパス |
| travel | 15 | 旅館の予約者情報、パンフレット請求、ツアー申込 |
| gov | 7 | 自治体・公共施設のイベントや講座の申込 |

## 道具

| ファイル | 役割 |
|---|---|
| `extract_form.py <html> <url> <category>` | HTML 1ページから、値なしの構造 JSON を標準出力へ書く。標準ライブラリのみ。 |
| `render.sh <url> <out.html>` | ヘッドレス Chrome（使い捨てのプロフィール）で1回 GET し、スクリプト実行後の DOM を保存する。 |
| `profile_score.py <json>...` | プロフィール系の欄（氏名・住所・電話など）の数を返す。4以上を「使える」とした。 |
| `collect.sh <category> <url>` | robots.txt の確認 → 静的取得 → 足りなければ描画 → 足りなければフォームらしいリンクを1段だけたどる → 抽出・採点・記録。HTTP 200 以外や、タイトルが 404・「見つかりません」のページは除外する。同じ URL は二度試さない。 |
| `eval/to_tsv.py <json>...` | JSON を、Chrome が Android に渡す手掛かりの近似（label、placeholder、aria-label、name、id、autocomplete）に平らにする。ラジオとチェックボックスは除く。 |
| `../test/dev/ryu/jevprobe/CorpusEval.java` | 上の TSV を標準入力で受け、probe の `Policy`（端末内ルール）で `localChoice` → `refine` する。32欄を超えるフォームは `TOO_MANY` と出す（製品の TOO_MANY_FIELDS に合わせた）。 |

再実行の手順（`probe/corpus/` で実行）:

```
J="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin"
"$J/javac" -nowarn --release 8 -encoding UTF-8 -d ../.build/eval ../src/dev/ryu/jevprobe/Policy.java ../src/dev/ryu/jevprobe/Profile.java ../test/dev/ryu/jevprobe/CorpusEval.java
python3 eval/to_tsv.py $(cat eval/usable.txt) | "$J/java" -cp ../.build/eval dev.ryu.jevprobe.CorpusEval > eval/all-before.tsv
```

収集の追加: `./collect.sh <category> "<検索結果に実際に出た URL>"`。取得した HTML は Claude のセッション用一時フォルダー（`collect.sh` 内の `H=`）に置いている。別環境では `H` を書き換えること。

## 現時点の結果（ベースライン）

- 32欄以下のフォームにある、プロフィール系らしい欄 805 のうち **354（43%）が UNKNOWN**。合成ページでは全欄が判定できていたので、実フォームには足りない。
- 32欄を超えて丸ごと対象外になるフォームが 156中 11。長い申込や見積のフォームでは候補がまったく出ない。
- UNKNOWN の主な原因（近似による分類）:
  1. ラベルが取れず、name/id にだけ手掛かりがある: 188欄。例 `dwfrm_profile_customer_lastname`、`ctl00$…$tbUserMailAddr`。いまの判定は name 全体を1語として照合していて、単語に分けていない。
  2. 語彙にないラベル: 91欄。例「西暦で生年月日を8桁入力・半角数字（例：19900103）」「丁目番地」「マンション名等」「お届け先名」。
  3. 入力例がラベル代わり: 35欄。例「（例：麻布）」「（例：はなこ）」。
  4. 括弧なしの「必須」や注記が付く: 35欄。例「都道府県 必須」「電話番号 必須 ※ハイフンなし」。いまは「（必須）」のような括弧書きしか取り除けない。

### この数字の限界（重要）

- `label` は近似で、`<label>` の文字列、なければ欄の直前の文字列を使っている。実際の Chrome は表組みのセルなどからラベルを推定して `label` 属性として渡すので、実機の UNKNOWN 率はこれとは違う。1 の188欄には「※」「必須」だけを拾ったものが多く含まれる。
- 「プロフィール系らしい欄」の判定は正規表現で、`ViewMailForm` の `Mail` に当たるような誤検出を含む。
- 正解ラベルはまだ付けていない。測れているのは UNKNOWN の割合だけで、**誤判定の割合は測れていない**。
- **Jev は一度も使っていない。** 端末内ルールだけの結果である。

## 収集で分かったこと（サブエージェントの運用）

- Haiku に取得と判断まで任せた1巡目は、URL を推測で作る（404）、案内ページだけを取って「全サイトが JavaScript 描画」と一般化する、他の担当の HTML を偽の URL で抽出する、数えていない割合を報告する、といった誤りが多かった。
- 2巡目は Haiku の仕事を「検索結果にある URL を選んで `collect.sh` を実行する」だけに絞り、判断はスクリプトに寄せた。こちらは記録と実物が一致した。
- 取れにくいもの:
  - 自治体の申込: 外部のフォームサービス（kintone、LoGoフォーム など）で JavaScript 描画、画面が複数ステップに分かれる。
  - 大手 EC: SPA で、会員登録にログインや同意の画面を挟む。

## 次にやること（Jev の試験に引き継ぐ場合）

1. **実機の手掛かりで測り直す**: 保存済みの描画後 HTML から script を除き、送信先を無効化してローカルで配信する。それをエミュレーターの Chrome で開き、probe の値なし診断ログ（`setprop log.tag.JevProbe DEBUG`）で、Chrome が各欄について実際に渡す手掛かりを記録する。これが正しいベースラインになる。
2. **正解ラベルを付ける**: 一部の欄に人手（または別モデル＋人の確認）で正しい種類を付け、UNKNOWN 率だけでなく誤判定率も測る。
3. **端末内ルールを直す**: 括弧なしの「必須」「任意」「※…」の除去、name/id を `_ $ [ ] -` と camelCase で単語に分けて照合、語彙の追加、32欄上限の見直し（上限を超えたら全体を拒否せず、プロフィール系の欄だけに絞る等）。
4. **UNKNOWN の欄だけを Jev に問い合わせて評価する**: 同じコーパスで、Jev が何欄を正しく解決したか、何欄を誤ったかを数える。これまでの実績は `ambiguous.html` の2回で、2回とも UNKNOWN か低確信度だった（VERIFICATION.md）。問い合わせの渡し方から見直す必要があるかもしれない。

## 取り扱いの注意

- `raw/` は他社の公開ページの構造（ラベルや選択肢の文言）をまとめたもの。個人情報は含まない（メールや電話らしい文字列は、すべて入力例のプレースホルダーであることを確認済み）。**リポジトリにコミットするかは未決定。**
- 取得した HTML そのものはプロジェクトの外（セッション用の一時フォルダー）にしか置いていない。
- 既知の不具合: `extract_form.py` の文字コード判定は先頭 4096 バイトの meta しか見ないため、ディノスのページの入力例1件が文字化けしている。
