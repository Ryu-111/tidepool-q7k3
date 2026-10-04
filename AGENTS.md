# jev-autofill 開発ルール（Claude Code / Codex 共通）

Bitwarden（Chrome拡張・Android）を個人用に改修し、本人プロフィールとサイト別ログインを一括入力する。合意した製品の動作は [README.md](README.md)、作業分担と経緯は [COORDINATION.md](COORDINATION.md)、検証範囲は [VERIFICATION.md](VERIFICATION.md)、Chrome拡張は [CHROME.md](CHROME.md)、probeは [probe/README.md](probe/README.md)。

## 作業の入口

- 回答・ドキュメントは日本語。コード・識別子・コミットメッセージは英語（Conventional Commits）。
- 最初に README.md の「合意した製品の動作」と COORDINATION.md の末尾（最新の分担と未解決事項）を読む。
- シェルは `rtk` 経由。正確な出力・終了コードが必要なら `rtk proxy <command>`。

## リポジトリ構成

| パス | 内容 | Git |
| --- | --- | --- |
| `/`（ルート） | ドキュメント、`probe/`、`scripts/` | このリポジトリ |
| `android/` | Bitwarden Android。Jev実装は `app/src/main/kotlin/com/x8bit/bitwarden/data/autofill/jev/` | 独立した作業コピー、`jev-autofill-prototype` |
| `clients/` | Bitwarden clients。Jev実装は `apps/browser/src/autofill/jev/` と `apps/browser/src/autofill/popup/jev/` | 独立した作業コピー、`jev-autofill-prototype` |
| `sdk-internal/` | 公式SDK `8b9fa3e2`（ローカルビルド用） | 独立、編集しない |
| `reference/` | コミュニティのAPIサンプル。製品へ組み込まない | 独立、編集しない |

- `android/` と `clients/` には未コミットの変更がある。commit・stash・reset・ブランチ切り替えは依頼がある場合だけ。ルートの `.gitignore` で除外されているので、ルートで `git status` しても変更は見えない。各ディレクトリで確認する。
- 公式コードの既存の動作は引数の既定値などで維持し、Jev経路を追加する形で変更する。

## 担当分担

- 最新の分担は COORDINATION.md の末尾に従う。相手の担当範囲を編集するのは、ユーザーの依頼がある場合だけ。
- 作業結果は COORDINATION.md の**末尾に追記**する（同じ箇所の同時編集を避ける）。検証結果の詳細は VERIFICATION.md に書く。
- エミュレーターの操作は同時に1エージェントだけ。

## Jev照会の境界（製品の必須条件）

- 接続先は `https://openrouter.ai/api/v1/systemone`、model `jev-latest`、質問は `choice` 型に固定。別モデルへのフォールバックはしない。リダイレクト拒否・`credentials: "omit"`・応答サイズ上限・タイムアウトを外さない。
- 端末のルールを優先し、決まらない（UNKNOWN の）欄だけを照会する。照会対象がなければ通信しない。1要求24問まで。質問キーは `field_no_N`（ページの name と衝突させない）。
- 送ってよいのは、ページ側にある欄の説明（ラベル・aria-label・直前の文字列・legend・placeholder・name・id・autocomplete・type・maxlength・選択肢、各200字以内）だけ。
- **送らないもの**: プロフィールの実値、ログイン情報、ページのURL、パスワード欄、APIキー（認証ヘッダー以外）、本文・画像・履歴。`AutofillView.Data` と `CipherView` を直列化しない。
- 応答は厳密に検証し、一つでも不正なら応答全体を捨てる。確信度0.6未満は使わない。キーなし・通信失敗時は端末ルールだけで入力する。
- 入力の条件: 保管庫の解錠、登録済みHTTPSオリジンの照合、入力直前の欄の再検証。非表示欄・別オリジンのiframeに入れない。既存値を無断で上書きしない。自動送信しない。OTP（`totpManager`、クリップボード）を呼ばない。入力禁止リスト（`JevBlocklist`）はJev候補にも適用する。
- 追加プロフィールは既存Cipherの暗号化カスタムフィールドに保存し、キーは両クライアントで `JevCustomFieldKeys.kt` の `jev.*` を共有する。独自の暗号化・同期・SDKレコードは作らない。
- probe の許可条件（`com.android.chrome` / `http` / `localhost`）は試験専用。製品へコピーしない。

## 秘密情報

- ルートの `.env`（`OPENROUTER_API_KEY=` の1行、権限600）は読まない・表示しない・コピーしない。接続確認は `rtk proxy python3 probe/live_check.py`（キーと応答本文を出力しない）。
- キーをAPK・fixture・ログ・テスト・ドキュメントに入れない。保管庫の実データを使わず、試験は合成データ（ダミーID「Jev試験」など）で行う。
- 実API（OpenRouter）を叩く試験は課金されるため、ユーザーの依頼があるときだけ実行する。通常の単体テストはモック／ローカル通信。
- `*.jks`、`*.keystore`、`user.properties` は読まない。

## コマンド

```sh
# probe（ルートから）
rtk proxy python3 probe/build.py                          # JVMポリシー試験 + APK
(cd probe && rtk proxy python3 -m unittest -v test_live_check.py test_emulator_key.py)
PROBE_SERIAL=emulator-5554 PROBE_CHROME=1 rtk proxy python3 probe/smoke.py   # 端末E2E（LOCAL）

# Android（android/ で）
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME=$HOME/Library/Android/sdk \
  rtk proxy ./gradlew --offline --no-daemon --max-workers=2 -I ../scripts/local-sdk.init.gradle \
  :app:testStandardDebugUnitTest --tests '*Jev*Test'
# 同じ環境変数で :app:detekt / :app:assembleStandardDebug

# Chrome拡張（clients/ で。Node は ../.tools/node-v24.17.0-darwin-arm64/bin を PATH の先頭に）
rtk proxy npx jest --config apps/browser/jest.config.js --runInBand apps/browser/src/autofill/jev apps/browser/src/autofill/popup/jev
rtk proxy npx eslint apps/browser/src/autofill/jev apps/browser/src/autofill/popup/jev
rtk proxy npx tsc --noEmit -p apps/browser/tsconfig.json
rtk proxy python3 ../scripts/build-chrome.py              # 本番モードでビルド・ZIP（約15分）
```

- SDKのローカルビルド: `rtk proxy python3 scripts/build-local-sdk.py`（GitHubトークンは使わない）。
- エミュレーターは `-gpu swiftshader_indirect -feature -Vulkan -no-window` が安定。試験後はエミュレーターを止め、自動入力サービスを元に戻す。

## 既知の落とし穴

- `chrome.scripting.executeScript` に渡す関数（`jevPage`）を `async` にしない。ビルド後に `__awaiter` を参照して実行時に失敗する。`jev-page.spec.ts` の `new Function` 再構築試験を残す。
- `doAutoFill` の `didAutofill` は送信を始めた結果で、入力成功の確認ではない。E2EはDOMの値で判定する。
- Chrome は `<input type=radio>` を Android 自動入力へ渡さない。郵便番号から住所を補完するページは、一括入力の後に住所欄を上書きすることがある。

## 検証と報告

- 変更した振る舞いと失敗経路を最小のテストで確認してから完了とする。Kotlin（detekt・Gradle）はフックで検査されないので手動で実行する。
- 次を混同しない: 単体テスト／端末E2E、LOCAL／`JEV LIVE（通信なし）`／Jevへの実照会、エミュレーター／実機、localhost／HTTPS実サイト。未確認の範囲は未確認と書く。

## 開発ハーネス（jh / jev-router）との関係

`~/development/jev-router` の `jh` がグローバルフック（`~/.claude/settings.json`）としてこのリポジトリでも動く。

- PreToolUse(Agent): Jevがサブエージェントのモデルを選ぶ。UserPromptSubmit: モデル変更を提案することがある。
- PostToolUse: 編集したファイルを Prettier で整形（`clients/` の設定を使う）。Stop: 編集した TS/JS に ESLint を実行し、通れば Jev が完了を判定する。未完了と判定されると差し戻される。
- これらは依頼文（最大8000字）・最後の応答（最大4000字）・編集したファイル名を OpenRouter 経由で Jev に送り、`~/.jev/ledger` に本文を7日保存する。プロンプトや応答に秘密情報・保管庫データを書かない。
- リポジトリ直下に `.jev-off` を置くと Jev への送信と記録が止まる。Stop フックだけ止めるときは `JH_STOP_HOOK=off`。
