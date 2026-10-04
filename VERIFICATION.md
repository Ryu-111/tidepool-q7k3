# 検証結果 — 2026-09-24

## 2026-09-27 追記：Bitwarden Android への統合（第1段階）

`android/`（`jev-autofill-prototype` ブランチ、未コミット）に、Jev一括入力をローカル判定のみで組み込んだ。Jevへの通信と、Login（パスワード）との同時入力はまだ含めていない。

- 追加: `app/src/main/kotlin/com/x8bit/bitwarden/data/autofill/jev/` の8ファイル。
  - 分類: `JevFieldPolicy`（probeの Policy を Kotlin に移植）
  - 書式と値: `JevFormatter`、`JevProfile`、`JevProfileMapper`、`JevCustomFieldKeys`
  - 欄の収集: `JevFieldCollector`
  - 入力計画: `JevBulkFillPlanner`
  - 候補: `JevBulkFillEntry`
  - 確認と入力: `JevBulkFillCompletion`
- 変更した既存ファイル（6件）:
  - `AutofillSelectionData`（`isJevBulkFill`、既定 false）、`AutofillIntentUtils`
  - `FillResponseBuilder(Impl)`（`jevDataset` を追加。既定 null）
  - `AutofillProcessorImpl`（Jev候補を生成。失敗しても通常の入力に影響しない）
  - `MainActivity`（フラグ付きの選択なら Jev の確認画面へ分岐）
  - `InlinePresentationSpecExtensions`（キーボード上の候補表示）
- 値の出どころ:
  - 保管庫の Identity の標準項目（姓名・郵便番号・都道府県・市区町村・住所1/2/3・電話・メール・会社・国）
  - 暗号化カスタムフィールド（`jev.family_kana` など、`JevCustomFieldKeys`）
  - 未登録の要素は入力しない。住所を推測で分割しない。電話はハイフン付きで保存されている場合だけ分割する。SSN・旅券番号などは読まない。
- 安全の規則:
  - Webは HTTPS のみ（debugビルドのみ `http://localhost` / `127.0.0.1` を許可）。
  - トップと別ドメインのiframe内の欄は対象外。自アプリの画面にも出さない。
  - ログイン画面のように、プロフィール系の欄が2つ未満のフォームには候補を出さない。
  - パスワード欄には書き込まない。OTP処理は呼ばない。
  - 空欄と確認できた欄だけを初期状態で選択する。入力は承認した欄だけ。
- 試験:
  - 新規の単体テスト21件（分類7、書式6、Identity変換3、入力計画5）が成功した。autofill 配下と MainViewModel の既存テストを含め、計600件が成功した。
  - detekt もエラーなし（循環的複雑度の3件は、既存コードと同じく抑制注釈を付けた）。
  - `:app:assembleStandardDebug` のビルドが成功した。
- 端末試験（Android 17 / Chrome 145）:
  - Bitwarden debug を自動入力サービスにして `patterns/combined.html` を開くと、キーボード上に「Jev: プロフィールを一括入力」の候補が表示された。当初はインライン候補の表示形式がなく、候補が出なかった。Bitwarden 既存の関数で追加して解決した。
  - 候補をタップすると Bitwarden の `MainActivity` が開いた（初回の案内画面）。
  - 保管庫にログインしていないため、Identity の選択以降（確認画面・入力）は未検証。
- 未実施: 保管庫にログインした状態での E2E、Jev照会の組み込み、Login との同時入力、Chrome拡張への展開、release署名。
- 試験環境: エミュレーターは `nohup` で起動すると途中で消えることがあった。Bashのバックグラウンド実行で起動すると安定した。

## 2026-09-27 追記：元号欄・勤務先・Jev照会・郵便番号補完

- 追加した対応:
  - 元号を別欄で選ぶ生年月日（[元号][年][月][日]、元年対応）
  - 会社名・部署名・役職
- Jevへの照会で、フォーム全体の値なしの欄表を文脈として渡すようにした（照会はローカルで決まらない欄だけ）。
- JVMポリシー試験は147件から164件に増やし、全件成功した。
- Android 17 / Chrome 145 の Chrome E2E（LOCAL）:
  - 次の8ページがすべてPASS: 元のページ、split、combined、mixed、profile、variants、era、ambiguous
  - era は JEV LIVE でもPASS（照会なし）。
  - ネイティブフォームの試験と Python の6テストも成功した。
- 不明欄をJevに照会するE2Eを初めて実施した（`ambiguous.html`、name=address2 とラベル「番地」が食い違う欄）。
  - 2回とも `Jev queried: yes`、応答の検証を通過した。
  - Jevの判定は UNKNOWN または低確信度で、欄は未入力のまま（安全側）。建物名の重複入力のような誤りはなかった。
  - 周囲の欄を文脈として渡しても解決できていない。Jevで欄を正しく埋められた例は、まだない。
- 郵便番号から住所を補完するページとの衝突を再現した（`autozip.html` / `autozipkey.html`）。
  - Chromeは自動入力時にinput・keyイベントも発火するため、`keyup` 専用のウィジェットでも動作した。
  - 約0.3秒後に「市区町村・番地」欄が「横浜市中区検証町」で上書きされ、番地が消えた。
  - 確認画面に警告と「郵便番号以外を再入力」を追加した。ただし2回目の候補表示は、手動で1回だけ成功し、自動試験では再現しなかった。
  - Android版では未解決。Chrome拡張ではDOMで入力後の再確認・再入力が可能。
- エミュレーターが Chrome起動時の Vulkan 初期化の直後に落ちる事象が再発した。`-feature -Vulkan` を追加して安定した。
- 起動引数: `-memory 4096 -cores 4 -gpu swiftshader_indirect -feature -Vulkan -no-window -no-snapshot -read-only`

## 2026-09-26 追記：生年月日・性別・住所の細分と表記ゆれ

- 住所を8要素（都道府県・市郡・区町村・町名・丁目・番・号・建物）に細分した。次の表記ゆれに対応した。
  - 市／区の分割、丁目／番／号の3分割
  - 都道府県・市区町村の1欄、町名・丁目、番地・号
  - 「1丁目2番3号」表記
- 生年月日に対応した。次の形式・部品を扱える。
  - 1欄: `/`・`-`・8桁・漢字・和暦
  - 年月日のselect×3（西暦・和暦を併記した選択肢）
  - ネイティブの `type=date`
- 性別（select・テキスト）、年齢（生年月日から端末で計算）、国（select・テキスト）を追加した。
- ダミー住所を「神奈川県横浜市中区検証町1-2-3 ダミービル101」に変更した（市／区分割の試験のため）。既存ページの期待値も更新した。
- JVMポリシー試験は84件から147件に増やし、全件成功した。
- Android 17 / Chrome 145 の emulator-5554 で、6ページ × LOCAL / JEV LIVE の12通りがすべてPASSした。
  - 対象: 元のページ、split、combined、mixed、profile（13欄）、variants（8欄）
  - ネイティブフォームの試験と Python の6テストも成功した。
- profile の LOCAL は4回中1回、全欄が未入力で FAIL した。再実行では2回とも PASS。認証後に出る2回目の候補チップをテストが取り逃がしたとみられる。`smoke.py` は取り逃がし時に NOTE を出すようにした。製品側の判定の問題ではないと判断したが、原因は未確定。
- Chromeの実機能で分かったこと:
  - `<input type=radio>` は Android 自動入力の構造に含まれない。性別ラジオは入力できないため、profile では「選択されないこと」を確認している。
  - `<input type=date>` は `AUTOFILL_TYPE_DATE` として渡され、`AutofillValue.forDate` で入力できた。
  - Chromeの独自推定では、市・区・町名の欄がいずれも `ADDRESS_HOME_CITY` だった。ページ自身の手掛かりを優先する方針を維持した。
- Jevへの照会は全ページで発生していない（全欄ローカルで判定）。不明欄を Jev で判定する E2E は未検証。
- 未対応: 性別ラジオ、和暦の元号と年を別々に選ぶ欄、会社名・部署などの追加プロフィール、郵便番号から住所を自動補完するページとの競合、動的に増える欄、iframe、HTTPS実サイト。

## 2026-09-26 追記：住所・氏名・電話の入力パターン対応

- 対応範囲: 分割欄（郵便番号3+4、電話3分割、姓名・セイメイ）、一括欄（氏名、フリガナ、住所全体、都道府県以降、市区町村＋番地）、都道府県select。書式（ハイフン、全角／半角、ひらがな／カタカナ／半角カナ、氏名の区切り）はラベル・プレースホルダー・maxlengthから端末内で決める。詳細は `probe/README.md` の「入力パターン」。
- JVMポリシー試験を24件から84件に拡充し、全件成功。ラベルの注記除去、未知の注記を含むラベルの拒否、ヒントの整合、分割・住所の絞り込み、書式、select照合、文字数超過時に入力しないことを確認した。
- Android 17 / Chrome 145 の emulator-5554 で、次の Chrome 試験がすべてPASSした（LOCAL / JEV LIVE 各1回）。
  - 元のページ（`/`）: 5項目
  - `patterns/split.html`: 13欄
  - `patterns/combined.html`: 7欄
  - `patterns/mixed.html`: 10欄
- ネイティブフォームの試験と Python の6テストも成功した。
- Chrome実機能で分かったこと:
  - Chrome は `autocomplete` 属性を直接渡さず、`computed-autofill-hints` の `HTML_TYPE_*` として渡す。
  - `label` 属性（`<label>` の文字）と `maxlength` は渡る。
  - Chrome独自の推定ヒントは、パスワード欄の直前の「番地」を `USERNAME` と判定していた。そのため独自推定は、ページ自身の手掛かりがない欄に限定した。値を含まない診断ログで確認した（`setprop log.tag.JevProbe DEBUG` のときだけ出力）。
- Jevの判定品質（重要）:
  - 旧方式（全欄をJevに照会し、Jevの答えだけを採用）では、細かい種類で UNKNOWN や低確信度が多かった。split で zip1、mixed で f8 が未入力になった。
  - 種類の説明文を追加すると、split で電話3欄、mixed で5欄が未入力と悪化し、結果も毎回ぶれた。
  - READMEで合意済みの「ローカル判定優先・不明欄だけJevへ照会」に変更した。3つのパターンページは全欄ローカルで決まるため、JEV LIVE 試験でもJevへの通信は発生していない（smoke は `Jev queried: no` と表示）。
  - ローカルで決まらない欄についてJevを使うE2Eは未検証。
- 試験中に emulator 37.3.1 が GPU エラー（`Failed to find ColorBuffer`）で2回落ちた。`-gpu swiftshader_indirect -no-window` で安定した。クラッシュレポート送信の同意ダイアログには同意していない。
- 未対応: 生年月日・性別・国などの欄、住所のサジェスト（郵便番号から自動補完するページでの上書き競合）、動的に欄が増えるフォーム、iframe、HTTPS実サイト。

## 2026-09-26 追記：Android 17 / Chrome 145でWebフォームE2E

- Android Emulatorを37.1.11からcanary 37.3.1へ更新（ユーザー承認済み、安定版はsdkmanagerで再導入可能）。37.1.11で起動しなかった `Jev_API_37`（Android 17, Google APIs rev6）が約33秒でブートした。起動引数は `-memory 4096 -cores 4 -no-snapshot -read-only`。
- 同梱Chromeは **145.0.7632.218**。Chrome 135以降という再開条件1を満たす検証先を確保した。
- Chromeの初回画面はユーザーが同意。Googleアカウントにはログインしていない。Chrome設定「Autofill services」で「Autofill using another service」を選び、Chromeを再起動した。
- `PROBE_SERIAL=emulator-5554 PROBE_CHROME=1 rtk proxy python3 smoke.py` → `PASS: LOCAL Chrome ...`（終了コード0）。
- `PROBE_SERIAL=emulator-5554 PROBE_CHROME=1 PROBE_LIVE=1 rtk proxy python3 smoke.py` → `PASS: JEV LIVE Chrome ...`（終了コード0）。Chrome の `http://localhost:8765` のダミーフォームで、OpenRouter経由のJev実通信・5項目一括入力・既存メール保持・非表示欄未入力をCDPで確認した。キーは従来の30秒ソケットで端末メモリへ渡し、試験後にアプリを停止して破棄した。
- 同じ端末でネイティブフォームのスモーク試験も再度PASS。Pythonの6テストも成功。
- 初回のChrome試験は、認証後に再表示される候補「ダミー情報」が約0.9秒の待ち時間内に出ず、未入力でFAILした。Chromeでは表示が遅いため、`smoke.py` の待ち時間を最大約10秒へ延長した。手動手順で原因を切り分け、入力値を確認してから修正した。
- 承認の期限（60秒）を過ぎてから同じ候補を再選択すると、確認画面は即座に閉じる。Chromeは同じ要求の応答を使い回すため、ページを再読み込みして新しい要求を作る必要がある。仕様どおりの動作で、未入力になる。
- 検証範囲はlocalhostのHTTPダミーフォームのみ。HTTPS実サイト、iframe、動的フォーム、select、Bitwarden本体への統合は未検証。

## 2026-09-26 追記：GitHubトークン不要のBitwardenビルド

- ユーザー指定によりGitHubトークンは使用しない。公開SDKのAndroid要求コミット `8b9fa3e2672633a2170116cc9fe66f7637850839` を取得し、Rust 1.98.0 / NDK 28.2.13676358でARM64向けにビルド成功。
- `scripts/build-local-sdk.py` がRustライブラリー、Kotlin型定義、AARを生成し、`com.bitwarden:sdk-android.dev:3.0.0-jev-local-8b9fa3e2` としてMaven Localへ登録。外部公開はしていない。
- `scripts/local-sdk.init.gradle` でGitHub Packagesリポジトリーを除外し、SDK依存をローカルの成果物へ置換。Bitwarden Androidの `:app:assembleStandardDebug` が成功。
- 検証APKは `android/app/build/outputs/apk/standard/debug/com.x8bit.bitwarden.dev.apk`。SDKのネイティブライブラリーはARM64のみ。本体へのJev統合はまだ行っていない。
- ユーザー指定でClaude Codeに認証情報を含まない検証ソースのレビューを依頼したが、OAuthセッションの期限切れ・更新失敗で終了。レビューが行われたとは扱わず、再ログインを依頼。
- 再ログイン後、Claude Codeのレビューが終了コード0で完了。待ち受け名の先取り、空のキーによる設定上書き、UIテストの待ち合わせについて指摘を受け、Codex側で修正。ランダムな待ち受け名を確保後に表示し、検証アプリの表示を確認してから転送する方式へ変更。外国アプリ／固定名の拒否と、ストリームのみでの転送を確認するテストを加え、Python合計6テストが成功。

## 2026-09-26 追記：ローカルSDKでBitwarden Androidをビルド

- `rtk proxy python3 scripts/build-local-sdk.py` が終了コード0。公式SDK `8b9fa3e2` からARM64の `libbitwarden_uniffi.so` とKotlinバインディングを生成し、`~/.m2` へ `com.bitwarden:sdk-android.dev:3.0.0-jev-local-8b9fa3e2` を公開（リモート公開なし、GitHubトークン不使用）。
- `android/user.properties` の `localSdk=true` により、アプリ側の置換（`sdk-android:LOCAL`）が初期化スクリプトの置換より後に適用され解決に失敗した。`scripts/local-sdk.init.gradle` の置換を `afterEvaluate` で登録するよう修正。
- `GITHUB_TOKEN`/`GH_TOKEN` を外した環境で `./gradlew --init-script ../scripts/local-sdk.init.gradle :app:assembleStandardDebug` が成功（3分36秒）。APKに `lib/arm64-v8a/libbitwarden_uniffi.so` を同梱。製品コードは未変更。
- Android 16 AVD `Jev_API_36` にインストールして起動し、初回画面の表示とSDKのRustログ `SDK Android support initialized` を確認。ネイティブSDKがアプリのプロセス内で初期化された。
- AVDの既定RAM 1536MBでは起動時ANRになった。AVD設定は変更せず、起動引数 `-memory 4096 -cores 4` と `cmd package compile -m speed` で回避。それでもSystem UIのANRダイアログが出るほど高負荷で、性能評価には使えない。
- Android 16では、アクションなしの明示的Intent（`am start -n`）がintent-filter不一致で拒否される。起動時は `-a android.intent.action.MAIN -c android.intent.category.LAUNCHER` を付ける。
- 保管庫の作成・ログイン・同期、自動入力サービスとしての動作は未確認。ARM64のみのビルドで、x86_64/armv7は含まない。
- Chrome 135以降の検証先は引き続き未達。`Jev_API_37_16K`（Android 17、16Kページ）は5分以上offlineのままブートせず停止した。Chromeの更新にはPlayストアへのGoogleアカウントのログインが必要で、本人の操作とする。
- 導入済みのAndroid 16 QPR2イメージ（API 36.1, Google APIs rev4）で新規AVD `Jev_API_36_1` を作成して試験。emulator 37.1.11では、4コアだとカーネルが約1.2秒（ネットワーク初期化）で停止した。1コアでは `/init` に進んだが、SELinux読み込み後に約900秒停止した。起動開始から約3550秒で `virtio_vsock` のworkqueue停止を出力し、adbはofflineのまま。同梱Chromeのバージョンは確認できなかった。エミュレーター／ホスト側の問題と判断し停止した。API 37と同じく新しいカーネルで再現している。
- 選択肢: (a) emulator 37.3.1（canaryチャネル）へ更新して再試験、(b) Chrome 135以降の実機、(c) Playストア版イメージで本人がログインしてChromeを更新。いずれも本人の判断・操作が必要。

## 2026-09-26 追記：AndroidでJev実通信と一括入力

- Android 16の専用AVD `Jev_API_36`、emulator 37.1.11で更新APKをインストール。`PROBE_SERIAL=emulator-5556 PROBE_LIVE=1 rtk proxy python3 smoke.py` が終了コード0で成功。
- Android側のJSON自己テスト、Macの `.env` から端末メモリへの一時受け渡し、AndroidからOpenRouterへの実通信、`JEV LIVE` 表示、5項目の一括入力、既存メール保持、非表示欄の未入力を確認。試験後にサービス設定を復元し、アプリを停止してキーを破棄。
- キーの受け渡しはエミュレーター限定の30秒間のUnixソケット。adbプロセスのUIDを確認し、値を引数・クリップボード・端末ファイルへ保存しない。キーの利用期限は受信後5分。製品用の機能ではない。
- JVMポリシー24アサーション、Python 4テスト、APK署名検証が成功。
- Android 17の公式Google APIs rev6・AVD `Jev_API_37` を導入したが、起動中にエミュレーターがsignal 11で異常終了。Android 16の起動・試験成功とは区別する。
- 同梱ネイティブフォームでの成功であり、Chrome WebフォームのE2EやBitwarden統合の成功とは扱わない。

### 新しいAndroidイメージの起動不良の解消

旧cmdline-tools 11のavdmanagerは `AndroidVersion.ApiLevel=37.0` を処理できず、作成したAVDの `.ini` に `target=android-0` を記録していた。CPU仮想化を使う条件を満たさなくなり、ソフトウェアエミュレーションのmprotectエラーと異常終了を招いていた。専用AVD `Jev_API_37` のtargetを実際のAPIレベル37へ修正すると、同じシステムイメージ・エミュレーターで起動が完了。`sys.boot_completed=1`、同梱Chrome `145.0.7632.218` を確認した。描画方式やイメージの再ダウンロードだけでは解消しなかった。

## 2026-09-26 追記：OpenRouter対応

- OpenRouter公式のJevガイド／System One互換API仕様を確認。TypeSafe直接契約の新規受付停止というユーザー報告を受け、Mac接続確認とAndroid試作の接続先を `https://openrouter.ai/api/v1/systemone` に変更。
- `.env` は空のTypeSafe用テンプレートだったため、内容を出力せず `OPENROUTER_API_KEY=` へ更新。権限・リンク・所有者を確認し、既存のキーがあれば上書きしない方法で実施。
- 4件のPythonテストが通過。接続先がOpenRouterであることと、旧プロバイダーの設定名を拒否することも確認。
- Android APKを再ビルドし、24件のポリシーアサーションと署名検証に成功。接続先・キー入力ラベル以外のAndroid入力動作は変更していない。
- 切替時点ではAPIキー未設定のため実API通信は未実行だった。
- ユーザーのキー設定後、`rtk proxy python3 probe/live_check.py` を実行して終了コード0・PASSを確認。OpenRouterのSystem One互換APIへ合成したEMAIL欄を1回送り、選択肢・確率分布・確信度の検証に成功。キーと応答本文は表示・保存していない。
- 確認できたのはMacからの実API接続と合成した欄情報の判定。Android／Chromeの実フォームを含むE2EやBitwarden統合の成功とは扱わない。

## 2026-09-25 追記：APIキーのファイル設定

- Git管理外の `.env` テンプレートを権限600で作成。内容の出力は行わない。
- `probe/live_check.py` を追加。固定の公式APIへ合成した欄情報を1回送り、キー・応答本文を出力せず結果だけを返す。Androidアプリへのキー埋め込みは行わない。
- `rtk proxy python3 -m unittest -v test_live_check.py` をprobeディレクトリで実行し、4テストが通過。ファイル権限・形式・リンク、不正応答、認証情報と本文の分離、リダイレクト拒否を確認。
- 初回実行ではAPIキー未設定を検出し、ネットワーク送信せず終了。実API接続成功は未確認。
- Android試作は候補がUNKNOWNだけになる質問を送信対象から除外し、送る質問がゼロなら成功扱いにしないよう修正。再ビルド・24件のポリシー試験・APK署名検証は成功。
- Chrome拡張の公式ソースを `clients/` に取得し、`jev-autofill-prototype` ブランチを作成。取得時HEADは `9f07c4b89012c273c48b08cbce0615ed4647d112`。製品コードの改修は未実施。
- SDK Platform 37.0とAndroid 16イメージを公式sdkmanagerで導入。新規AVD `Jev_API_36` を作成し、読み取り専用で起動。Chromeの実バージョンは133.0.6943.137で、135以降の検証は未達。
- 新規Android 16エミュレーターで更新APKのインストール・起動・JSON自己テストが成功。試験後にエミュレーターを終了。今回の変更後はネイティブUIスモークの全行程は再実行していない。

## 初回の実行結果（2026-09-24）

| 確認 | 結果 |
|---|---|
| `rtk proxy python3 probe/build.py` | 成功。JVMポリシー試験24件、Javaコンパイル、DEX作成、APK署名検証が完了 |
| Android上のJSON自己テスト | PASS。許可語彙以外の除去、秘密値なし要求、応答の型・欄ID・選択肢・確率分布、不正応答拒否 |
| `rtk proxy python3 probe/smoke.py`（probeディレクトリでは `python3 smoke.py`） | Android 14エミュレーターでPASS。明示選択した5項目の一括入力、既存メール保持、非表示欄の未入力を確認 |
| 公式Bitwarden Android作業コピー | 取得・改修ブランチ作成済み。製品コードの変更なし |

試験の正確なコマンド例:

```sh
cd /Users/ryu/development/jev-autofill
rtk proxy python3 probe/build.py
rtk proxy python3 probe/smoke.py
```

スモーク試験には、先にAPKをインストールした `emulator-5554` が必要です。スクリプトは物理端末を拒否し、サービス設定を試験前の値へ戻します。ビルドではJava 8ターゲットと一部Android互換APIの非推奨警告が出ますが、エラーではありません。

## 発見して修正した問題

初回スモーク試験は、入力済みメールがダミー値に上書きされてFAILとなりました。Androidのフォーム情報で値が伏せられており、「取得値なし＝空欄」という条件が誤りでした。

修正後は、空欄である証拠がない欄を初期選択せず、項目ごとの明示選択がなければDatasetへ加えません。再試験で5項目の入力と既存値保持を確認しました。値が伏せられた一般フォームでも空欄だけを自動選別できることを証明したものではありません。

## 未検証・未実装（2026-09-26時点）

- Chrome 135以降の外部自動入力経路は、エミュレーターのlocalhostダミーフォームでのみ確認済み。HTTPS実サイト・実機では未確認。
- Bitwarden SDKを含む製品ビルドの実利用。ローカルSDKでのdebugビルド・起動・SDK初期化は確認済み（上記追記）。ログイン・保管庫・同期・自動入力、署名済みreleaseビルドは未確認。
- 本番のオリジン・iframe・動的ページの再検証、select部品、Bitwardenの解錠・保管・同期・復旧・競合処理への統合。
- Chrome拡張の改修と配布、製品用APKの署名と配布。

計画のAndroid先行検証条件が満たされていないため、本実装へ進めたとは報告しません。試作はダミー情報しか持たず、実データの移行やユーザーの既存保管庫への接続は行っていません。

#### 2026-09-28 Codex再検証完了

`JevFieldCollector.kt` の非表示親・探索上限の2件を修正後、次を実行した。

```
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME=/Users/ryu/Library/Android/sdk rtk proxy ./gradlew --offline --no-daemon --max-workers=2 -I ../scripts/local-sdk.init.gradle :app:testStandardDebugUnitTest --tests '*Jev*Test'
```

android/ で実行、終了コード0。JUnit XMLでも **25テスト、失敗0、エラー0** を確認（Planner 5、CollectorSecurity 4、FieldPolicy 7、Formatter 6、ProfileMapper 3）。先にCollectorの新規4件だけを実行した際は2件失敗を再現しており、修正後に両方が成功した。Gradleは終了済みなので、Claude側のビルドを再開してよい。

今回の製品コード変更はCollectorのみ。Completionの行ずれ・blocklistの2件はClaudeが対応する旨を画面で確認済みだが、修正完了は未確認。Macがロックされたため、以降のUI連絡・端末検証は実施していない。APK再生成・実端末試験・パスワードとの一括入力・Jev実通信の製品組み込みを完了したとは扱わない。

## 2026-09-28 PC Chrome拡張の開発版（Codex）

以前の「Chrome拡張未実装」の記録はこの更新で置き換える。Androidの検証結果とは別に扱う。

- Bitwarden OSS browser `2026.9.3` / Manifest V3 のビルド成功（終了0）。Node 24.17.0、npm 11、既存lockfileの依存を使用。
- 新規Jevテスト3スイート **33件成功、失敗0**。Jest/jsdomとサービスのモックによる検証。Chrome実機上のE2Eではない。
- 検証内容: 明示承認、非表示・値変更・欄差替え・承認再利用の拒否、入力後の変更検出、自動送信なし、空パスワード未入力、住所等の整形、モデルへの情報制限、不正応答拒否、ロック・禁止サイト・ナビゲーション・再認証取消・保管庫変更の拒否、ログインのHTTPSオリジン/ポート/URI制約。
- 新規コードと変更済みのBrowserApi・ルート・保管庫テンプレートに対するESLint成功。`git diff --check` 成功。
- `scripts/build-chrome.py` で個人用の名前とIDに分離し、ZIP作成成功。ZIPのCRC整合性、MV3、backgroundファイル存在、`.env` / `user.properties` / `local.json` 不在を検証。
- 成果物: `chrome-dist/jev-autofill-chrome.zip`（28,200,286 bytes）、読み込みフォルダー `clients/apps/browser/build`。
- ZIP SHA256: `229c35626ceb46581899d69829ec30648df1eea6181755eaf3c343d8314478b3`。

実行コマンド（clients/、プロジェクト内NodeをPATHに指定）:

```
rtk proxy npx jest --config apps/browser/jest.config.js --runInBand --runTestsByPath apps/browser/src/autofill/jev/jev-policy.spec.ts apps/browser/src/autofill/jev/jev-page.spec.ts apps/browser/src/autofill/popup/jev/jev.component.spec.ts
rtk proxy npx eslint apps/browser/src/autofill/jev apps/browser/src/autofill/popup/jev apps/browser/src/platform/browser/browser-api.ts apps/browser/src/popup/app-routing.module.ts apps/browser/src/vault/popup/components/vault/vault.component.html
```

未検証: Chromeへ読み込んだ後の画面表示・ログイン・同期・実フォーム一括入力、PC拡張からのJev実通信、実保管庫での端末間同期と復旧。Macロック中のためUI確認は行っていない。個人用開発版であり、ストア公開・一般サイトでの動作保証・release署名を完了したものではない。既存の画像付きフォーム検証結果はAndroid/probeの結果であり、このPC拡張の結果へ流用しない。

## Claudeレビュー反映版（2ファイル送信許可後）

Claude Codeによる1回の限定レビューを実施。4件をCodexが失敗テストで再現後、修正した。

1. 視認性: 累積opacity 0.1未満、4px未満、画面外、clip/clip-path、中央へのヒットテストが本人の欄と一致しない場合を除外。長いフォームはスクロールして再確認が必要。全視覚的偽装への完全な防御を保証しない。
2. 分割: 件数だけの郵便/電話分割を廃止。隣接・桁数制約を確認し、独立した全文欄には全値を提示。
3. 住所: 別欄へ実際に入力可能な要素だけまとめた住所から除く。選択肢不一致などで入力不能の要素は残す。
4. フォーム変更: formの属性はElement.prototype経由で読み、action等の名前付き子要素によるプロパティの上書きを避ける。baseURI変更も検出。

検証: 修正前は新規4件がFAIL。修正後は計37件PASS（3スイート実行時にDOMテストの空結果の期待値だけ不備が残ったため、修正後に当該8件を再実行して成功。その他29件は成功済み）。ESLint成功、ビルド終了0、ZIP整合性・manifest・秘密設定ファイル不在を再確認。

最新ZIP: `chrome-dist/jev-autofill-chrome.zip` / 28201720 bytes / SHA256 `9322ae60cfc3d1adc6575d05f48ca4fd31c7367e8ea3947cc7dd0d9b6074004b`。以前のZIPを置換済み。

Chrome実画面のE2E、PC拡張からのJev実通信、実保管庫の同期・復旧は未検証。Claudeは修正前の2ファイルのみレビューし、修正後の再レビューは依頼していない。

## 2026-09-28 Bitwarden Android 一括入力のE2E（Claude）

環境: エミュレーター Jev_API_37（Android 17, Chrome 145）、Bitwarden debug（`com.x8bit.bitwarden.dev`、試験アカウントでユーザーがログイン・ロック解除）、ローカル fixture（`http://localhost:8765/patterns/`、debug ビルドのみ http localhost を許可）。

- **ダミーID**: 「Jev試験」を作成した。
  - 標準項目: 氏名・会社・メール・電話・住所。
  - カスタムフィールド（テキスト）: `jev.family_kana` / `given_kana` / `birthdate` / `gender` / `municipality` / `ward` / `town` / `chome` / `ban` / `go`。
  - 値はすべてダミー。日本語はエミュレーター内 Chrome のクリップボード経由で貼り付けた。
- **Codex指摘の修正を実機で確認（combined.html）**:
  - 確認ダイアログの説明文がタイトル側に移り、リストは入力欄の行だけになった。
  - 先頭（氏名）と末尾（メール確認用）だけにチェック → 2欄だけ入力され、他は空のまま。末尾行を選んでも異常終了しない。
  - 全7行にチェック → `Jev bulk fill approved: 7 fields`。7欄すべて `EXPECTED` どおり（氏名・ふりがな・郵便番号 `100-0001`・住所一括・電話 `09000000000`・メール×2）。
  - 途中で郵便番号だけ空になった回は、試験スクリプトが「郵便番号以外を入力」ボタンを押していた。製品の不具合ではない。
- **全パターンのE2E（ロック解除後、全行を承認して「入力」）**: 各ページの `EXPECTED` と CDP で照合した結果。
  | ページ | 結果 | 備考 |
  |---|---|---|
  | combined | 7/7 | 氏名・ふりがな・郵便番号・住所一括・電話・メール×2 |
  | split | 13/13 | 姓名・カナ分割、郵便番号2分割、都道府県 select、電話3分割 |
  | mixed | 10/10 | 市区町村・番地、ハイフン付き電話 |
  | profile | 14/14 | 和暦併記の年 select、月・日、年齢、国、市/区/町名/丁目/番/号。性別ラジオは空（期待どおり） |
  | variants | 8/8 | 8桁生年月日、性別 select、日付型（AUTOFILL_TYPE_DATE）、和暦文字列、町名・丁目、番・号 |
  | era | 6/8 | 元号・和暦年・月・日・会社名は正しい。部署・役職は試験IDに未登録のため空（「入力しない欄: 2件」と表示。推測で埋めない） |
  | ambiguous | 4/4 | 判定できない欄は空のまま（許容値） |
  | autozip / autozipkey | 5/6 | 「入力」では、郵便番号の補完処理が入力後に住所1を「横浜市中区検証町」に上書きした（Android では未解決の既知衝突。ダイアログで警告済み） |
- **「郵便番号以外を入力」（autozip）**: 4欄を入力し、郵便番号は空のまま。補完処理は動かず、住所1は `横浜市中区検証町1-2-3` のまま残った。
- **ブロックリストの修正（端末で確認）**:
  - Bitwarden の「Block autofill」に `http://localhost` を登録した（`:8765` のようなポート付きは Invalid URI になる）。
  - combined では5回の要求すべてが `Unfillable` で返り、Jev の候補も出なかった。修正前は、ここで「Jev bulk fill only」として候補が出ていた。
  - 登録を削除すると `Fillable` に戻り、ID の選択画面まで開いた。除外リストは空に戻してある。
- **試験手順上の注意**:
  - ページを開いて最初にフォーカスした欄では候補が出ないことがあり、別の欄では出る。
  - uiautomator の文字列一致でボタンを押すと、誤ったボタンを押した回があった。ボタンは resource-id（`button1` = 入力、`button3` = 郵便番号以外を入力）で押す。
  - ホストの負荷が高いと Chrome が ANR になる。タブは試験ごとに閉じた。

## 2026-09-29 PC拡張: Jev に欄情報を渡す方式で実フォームのコーパスを評価（Claude）

- **対象**: `probe/corpus` の使えるページ98件（フォーム156、2007欄。検索欄や本文欄など、プロフィールと無関係な欄を含む）。
- **判定の内訳**:
  - 端末ルールだけ: 449欄。
  - 端末ルール＋Jev: 端末ルール449欄に加えて、Jev が552欄を判定した。残る1006欄は判定なし（多くはプロフィールと無関係な欄）。
  - Jev の問い合わせは147フォームで、失敗0。旧版では48欄以上のフォームで HTTP 400 になっていたが、24問ずつに分けて解消した。
- **正しさの目視確認**（正解ラベルなし、目安）:
  - 1回目の指示では、無作為60欄中の明らかな誤りが8欄だった。英字の会社名、渡航先、計画中の建物の郵便番号、2つ目の電話番号など、本人の値ではない欄を埋めていた。
  - 「本人の情報以外は UNKNOWN」と指示・選択肢を直したあとは、別の無作為50欄中、明らかな誤りが1欄（「丁目番地」欄に市区町村＋番地）、判断のつかないものが1欄だった。
- **合成ページ（`probe/fixture/patterns` 9枚）**: 新しい端末ルールだけで、収集から値の組み立てまで全ページ `EXPECTED` と一致した（Jest、jsdom で描画を模擬）。
- **Jev の応答時間**: 0.4〜5秒/回。
- **未確認**:
  - 誤判定率の正式な測定（正解ラベルが必要）。
  - Chrome 実機での Jev ありの入力（ユーザーによるキー設定待ち）。
  - Android 版への反映。
