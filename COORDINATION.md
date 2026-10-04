# Codex / Claude 作業連携

## 2026-09-26 Codex確認

Claudeアプリの既存セッション「jev-autofill 続行」で、生年月日・性別・市区町村／丁目番号分割の実装とエミュレーターE2Eが進行中であることを画面から確認した。CLIの `claude agents --json` は空だったが、デスクトップのセッションは実行中だった。新しいClaudeセッションは起動していない。

- Claude担当: `probe/` の対応欄・書式・フィクスチャ・端末E2E。現在の変更を保持する。
- Codex担当: Bitwarden統合経路の読み取りと本ファイル。エミュレーターの操作、SDK更新、probeソースの編集は行わない。
- 連絡は既存Claudeの入力欄へ送信済み。実行中処理の次に読まれるキューに入ったことを確認。担当の了承・完了はまだ確認していない。
- Claudeからの結果追記は末尾に行う。同じ箇所の同時編集を避ける。

### 今回再確認した結果

`probe/` で `rtk proxy python3 -m unittest -v test_live_check.py test_emulator_key.py` は6件成功。外部通信を伴わず、接続先固定、キーの本文混入防止、リダイレクト拒否、ファイル検証、受信先アプリとランダム待ち受け名の照合を確認した。

最新のPolicy.java・Profile.java・PolicyTest.javaを一時ディレクトリにコピーし、JDK 21の `javac --release 8` と `java` で独立実行。**143アサーション成功**、試験前後の元ソースが同一であることも確認した。Claudeの `.build` や端末は操作していない。追加ページの端末E2EはClaudeが実行中で、今回の143件はJVM上の分類・書式試験である。

検証したSHA-256:
- Policy.java: `104ad5298437779042f34d72226275092ae55a50cbe2412d9889ab1782d31ba1`
- Profile.java: `31a3f57c046d5efc91d4d75ffb7b02130b38cef54589e5b4c38012584954a9ca`
- PolicyTest.java: `b65dbf391d10a52aeb980583b4e970c19b36130f40f7167c5dbf0408be0e4373`

## Bitwarden統合の具体的な注意点

2026-09-26の作業コピーを直接読んだ結果。以下は実装候補と検証条件であり、製品統合済みという意味ではない。

### Android

1. `android/app/src/main/kotlin/com/x8bit/bitwarden/data/autofill/parser/AutofillParserImpl.kt` はフォーカスに応じてLoginかIdentityの一方だけを選び、別の種類の欄を除外する。既存の `AutofillPartition` を単純に使うだけでは住所とパスワードの混在入力を実現できない。Jev一括入力を明示選択した経路で、双方の対象欄を保持する必要がある。
2. `data/autofill/manager/AutofillCompletionManagerImpl.kt` は単一の `CipherView` を受け、最初のfilledPartitionだけでDatasetを作る。一括入力用の確認画面でIdentityとLoginをそれぞれ選び、承認された欄だけを一つのDatasetに集約する。Cipherを合成して保管庫へ保存しない。
3. `data/autofill/provider/AutofillCipherProviderImpl.kt` は保管庫解錠、active項目、再認証不要条件、LoginのURIマッチを確認する。直接SDKで復号する独立経路は作らない。再認証が必要な項目は既存の本人確認を経由し、キャンセル時は入力しない。選択後のロック・アカウント切替でも結果を破棄する。
4. 同CompletionManagerは `totpManager.tryCopyTotpToClipboard` も呼ぶ。初版でOTPは対象外なので、そのまま呼び出すと不要な副作用になる。一括入力経路でOTP処理を呼ばず、既存の通常入力の動作は変えない。
5. `AutofillView.Data` や `CipherView` をAPIへ直列化しない。Jevへ渡す境界には一時ID・型・固定語彙だけを持たせる。パスワード欄はローカルでのみ処理する。

### Chrome拡張

1. `clients/apps/browser/src/vault/popup/services/vault-popup-autofill.service.ts` は `_internalDoAutofill` で再認証を扱うが、一項目の入力用で `fillNewPassword: true` と `allowTotpAutofill: true` を渡す。Jevの一括入力からこの既定の呼び方を流用しない。
2. `apps/browser/src/autofill/services/autofill.service.ts` の `doAutoFill` は `allowUntrustedIframe` が未指定ならiframe拒否の条件を満たさない。新経路は `allowUntrustedIframe: false`、`autoSubmitLogin: false`、`fillNewPassword: false`、`allowTotpAutofill: false` を明示する。OTPのクリップボード取得は別処理なので、この指定だけでOTP副作用がなくなるとは扱わない。
3. `onlyEmptyFields` と収集時の情報だけで承認後の変更を防げるとは限らない。入力直前にタブ・document/frame・HTTPSオリジン・可視性・型・現在値を照合する。承認されなかった欄へ値を送らない。
4. `doAutoFill` の `didAutofill` は送信を開始した結果で、ページ上の入力成功を示す確認応答ではない。E2Eの合格はDOM上の値と送信されていないことを別途確認する。

### データの保存

SDKの `sdk-internal/crates/bitwarden-vault/src/cipher/identity.rs` とブラウザーの `libs/common/src/vault/models/view/identity.view.ts` には、フリガナ・生年月日・性別・住所8要素専用の標準プロパティがない。

標準の姓名・住所・電話・メールは既存Identityを再利用する。追加情報は既存Cipherの暗号化されたカスタムフィールドを利用する案とし、両クライアントで同じキー・型を使う。住所を推測で分割して保存せず、本人が確認した要素を保持する。生年月日等が未登録なら未入力にする。国・性別を氏名や住所から推測しない。独自SDKレコードや新しい暗号化形式の追加は不要。

### 最小の次段階

まずAndroidのデバッグ版に、既存保管庫で選んだIdentityとLoginを同じ確認画面へ渡す経路を作る。専用の合成データで、解錠・再認証・ロック中断・HTTPSオリジン不一致・既存値保持・送信なしを通してからChrome拡張へ展開する。localhost限定のprobeの許可条件を製品へコピーしない。

現在のパターンページはローカルで解決できるため、`JEV LIVE（通信なし）` の成功をJev実通信と混同しない。不明欄をJevへ実際に照会するケースは独立して検証が必要。

## Claude結果追記

2026-09-26 Claude（probe担当）。エミュレーター・SDKの操作とprobeソースの編集はClaudeのみが行った。android/・clients/ は編集していない。

### 完了

- 住所8要素（都道府県・市郡・区町村・町名・丁目・番・号・建物）と組み合わせの種類を追加した。分割（郵便3+4、電話3、姓名、セイメイ、市／区、丁目／番／号、年／月／日）と、別欄の要素を除く絞り込みを `Policy.refine` で行う。
- 生年月日（1欄の各表記、和暦、年月日select、`type=date`）、性別・国（select・テキスト）、年齢（計算）を追加した。
- 書式（ハイフン、全角／半角、かな種別、区切り、丁目番号表記、日付）は端末内で決める。Jevへの要求には種類名と固定の英語の説明だけを入れる。
- Jev照会はローカル判定優先に変更した。ローカルで決まらず候補が2つ以上ある欄だけを照会する。照会対象がなければ通信しない。
- JVM試験147件が成功した（Codexの独立実行で143件を確認した時点から4件追加）。
- Android 17 / Chrome 145 emulator の Chrome E2E は、6ページ × LOCAL / JEV LIVE の12通りがすべて PASS。ネイティブフォームと Python の6件も成功した。
- 試験後、エミュレーターを停止し、Android の自動入力サービスを Google に戻した。

### 未解決・統合時の注意

1. 性別の `<input type=radio>` は Chrome が Android 自動入力へ渡さない（Android 17 / Chrome 145）。Android版でラジオへの入力は期待できない。Chrome拡張側では DOM で扱えるため、両クライアントで対応範囲が異なる。
2. JEV LIVE の成功は、いずれも「照会対象なし・通信なし」。不明欄を Jev で判定する E2E は未検証。旧方式（全欄をJevの答えで決める）では、細かい種類で UNKNOWN が多く、結果も毎回ぶれた。
3. profile の LOCAL で1回、2回目の候補チップの取り逃がしとみられる全欄未入力があった（再実行では PASS）。製品の確認画面で1回の選択で入力を完了する設計なら、発生しない可能性がある。
4. Chrome独自の推定（`ua-autofill-hints` / `computed-autofill-hints` の `HTML_TYPE_*` 以外）は、パスワード欄の直前の欄を USERNAME と、市・区・町名をすべて CITY と推定する。製品でも、ページ自身の手掛かりを優先する規則が必要。`autocomplete` は `HTML_TYPE_*` としてだけ渡る。
5. 保存形式の案（Identity＋暗号化カスタムフィールド）に合わせるには、`Profile.java` の要素（市郡／区町村、町名、丁目・番・号、生年月日、性別、国）と同じキーが要る。住所の分割結果は保存せず、本人が確認した要素を保存する方針に同意する。
6. probe の許可条件（`com.android.chrome` / `http` / `localhost`）は試験専用。製品へコピーしない。

### 2026-09-27 追記（Claude）

- 追加した対応: 元号の別欄選択（[元号][年][月][日]）、会社名・部署名・役職。Jevへの照会には、フォーム全体の値なしの欄表（種類・候補・ローカルで決まった種類）を文脈として含める。JVM試験は164件が成功した。
- Chrome E2E（LOCAL）は8ページがすべてPASS。era は JEV LIVE でもPASS。ネイティブ・Python 6件も成功した。
- 上記2の更新: `ambiguous.html` で不明欄のJev照会を実施した（2回とも `Jev queried: yes`）。応答の検証は通過したが、判定はいずれも UNKNOWN または低確信度で未入力のまま。誤入力はなかった。Jevで欄を正しく埋めた例はまだない。Jevは「決まらない欄を安全に空ける」以上の効果を確認できていない。
- 新しい未解決事項:
  - 郵便番号から住所を補完するウィジェットとの衝突。Chromeは自動入力時にinput・keyイベントも発火するため、`keyup` 専用でも発動した。一括入力の約0.3秒後に住所欄が「市区町村＋町名」で上書きされ、番地が消える。
  - Android版は1回の Dataset で全欄を入れるため防げない。確認画面に警告と「郵便番号以外を再入力」を追加したが、2回目の候補表示が安定しない（手動で1回成功、自動では再現せず）。
  - Chrome拡張では、入力後に一定時間DOMを再確認し、承認済みの欄だけ再入力する設計を推奨する。その際も、承認していない欄への書き込みや、ページが変えた値の無断上書きは避ける。本人に差分を示してから再入力する。
- 試験環境: emulator 37.3.1 は Chrome 起動時に Vulkan 周りで落ちることがある。`-gpu swiftshader_indirect -feature -Vulkan -no-window` で安定した。

### 2026-09-27 追記（Claude）：Android 統合の第1段階

- ユーザーの承認を得て `android/`（`jev-autofill-prototype`、未コミット）を編集した。`clients/` は未編集。Codexが `android/` を編集する場合は、以下のファイルとの競合に注意すること。
- 新規: `app/src/main/kotlin/com/x8bit/bitwarden/data/autofill/jev/`（8ファイル）と、`app/src/test/.../autofill/jev/`（テスト4ファイル）。
- 既存の変更: `AutofillSelectionData`、`AutofillIntentUtils`、`FillResponseBuilder(Impl)`、`AutofillProcessorImpl`、`MainActivity`、`ui/autofill/util/InlinePresentationSpecExtensions`。いずれも引数の既定値で既存の動作を維持する。
- Codexの注意点への対応:
  - 1（Partition を1つだけ選ぶ問題）: Bitwarden の Parser・Partition は変えず、Jev専用の収集器と入力計画で全欄を扱う。
  - 2（Cipher の合成）: Cipher を合成せず、1つの Dataset にまとめる。保存もしない。
  - 3（解錠・再認証）: 既存の保管庫選択の流れ（解錠・再認証）をそのまま通る。
  - 4（OTP）: `totpManager` を呼ばない。
  - 5（直列化）: `AutofillView.Data` と `CipherView` は直列化しない（Jev照会は未組み込み）。
- 保存形式: カスタムフィールドのキーは `JevCustomFieldKeys` に定義した（`jev.family_kana`, `jev.given_kana`, `jev.municipality`, `jev.ward`, `jev.town`, `jev.chome`, `jev.ban`, `jev.go`, `jev.birthdate`（ISO日付）, `jev.gender`（female/male/other）, `jev.department`, `jev.job_title`）。Chrome拡張でも同じキーを使ってほしい。
- 試験: 単体テスト600件（新規21件）と detekt が成功した。端末では候補の表示と、タップ後に Bitwarden が開くところまで確認した。保管庫にログインしていないため、確認画面と入力は未検証。

### 2026-09-28 Codex独立レビュー

既存Claudeセッションから担当の了承を受領。ClaudeがAndroid製品コードと端末UIを担当し、Codexは独立レビューと新規テスト `JevFieldCollectorSecurityTest.kt` のみを担当する。既存コード・保管庫・エミュレーターはCodexから操作していない。

確認済みの指摘（Claudeに修正依頼済み、修正前の記録）:

1. **P1: 承認する行がずれる／最後の行でクラッシュする。** `JevBulkFillCompletion.showConfirmation` は `setMultiChoiceItems` の後にListViewへヘッダーを追加する。Android SDKの `sources/android-34/com/android/internal/app/AlertController.java:1260-1265` はListViewの位置をそのまま `mCheckedItems[position]` とコールバックへ渡す。ヘッダーにより一つずれ、別の欄が承認され、最後の欄は配列外になる。補足文は行番号を変えないタイトル／独立ビューに置き、先頭・中間・末尾の選択と実際のDatasetが一致することを検証する。
2. **P1: 入力禁止サイトでJev候補が復活する。** `AutofillParserImpl:173-176` はユーザー設定と固定blocklistに一致すると `Unfillable` を返すが、変更後のProcessorは全Unfillableに対して独立にJev候補を作り返す。Collector/Entryはその禁止設定を確認しない。単なる未分類とポリシー拒否を区別するか、同じ禁止判定を候補生成前・入力確定前に適用する。通常入力とJevの両方が禁止される回帰試験が必要。

追加のCollector境界試験4件を作成し、対象限定のオフラインGradle試験を実行中。HTTPS別ドメイン除外、非localhost HTTP拒否、非表示の親の子を除外、探索上限を超えたとき部分入力を拒否する条件を検証する。認証情報・実データ・ネットワークは不要。

#### Codex試験結果と担当更新

4件を実行し、HTTPS別ドメイン除外・HTTP拒否はPASS、非表示の親と探索上限の2件はFAILを再現（Gradle終了1、テスト自体のコンパイル成功）。Codexが `JevFieldCollector.kt` のこの2点のみを修正して再検証する。Claudeは引き続きCompletionの行ずれとProcessorのblocklistを担当。MacがロックされたためUIへの追加連絡はできず、本ファイルで共有する。

修正: 非表示ノードは子孫ごと探索対象から除外し、2048ノード上限を超えた場合は `TOO_MANY_NODES` としてフォーム全体を拒否する。途中まで集めた欄で分割や入力を決めない。

#### 2026-09-28 Codex再検証完了

`JevFieldCollector.kt` の非表示親・探索上限の2件を修正後、次を実行した。

```
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME=/Users/ryu/Library/Android/sdk rtk proxy ./gradlew --offline --no-daemon --max-workers=2 -I ../scripts/local-sdk.init.gradle :app:testStandardDebugUnitTest --tests '*Jev*Test'
```

android/ で実行、終了コード0。JUnit XMLでも **25テスト、失敗0、エラー0** を確認（Planner 5、CollectorSecurity 4、FieldPolicy 7、Formatter 6、ProfileMapper 3）。先にCollectorの新規4件だけを実行した際は2件失敗を再現しており、修正後に両方が成功した。Gradleは終了済みなので、Claude側のビルドを再開してよい。

今回の製品コード変更はCollectorのみ。Completionの行ずれ・blocklistの2件はClaudeが対応する旨を画面で確認済みだが、修正完了は未確認。Macがロックされたため、以降のUI連絡・端末検証は実施していない。APK再生成・実端末試験・パスワードとの一括入力・Jev実通信の製品組み込みを完了したとは扱わない。

#### 2026-09-28 Claude: Codex指摘2件の修正

- **行ずれ（確認済み・修正）**: `JevBulkFillCompletion` でリストのヘッダーをやめ、説明文を `setCustomTitle` のタイトル領域へ移した。リスナーには `which in checked.indices` のガードも追加。エミュレーターでは修正前のダイアログで説明文がListViewの先頭行になっていることを確認した（ヘッダー構造の再現）。
- **blocklist（確認済み・修正）**: `AutofillParserImpl.BLOCK_LISTED_URIS` を `internal` に変更。新規の `JevBlocklist.isBlocked(uri, blockedAutofillUris)` で、組み込みの禁止リスト・ユーザーの除外リスト・URI不明（fail closed）を拒否する。
  - `JevForm.Fillable.uri` は `https://domain` または `androidapp://package` の形。
  - この判定は `JevBulkFillEntry` で候補を作る前と、`JevBulkFillCompletion`（MainActivity から `settingsRepository.blockedAutofillUris` を渡す）の両方で行う。
  - Processor は除外リストを遅延読み出しのラムダ（`JevDatasetProvider` の第4引数）として渡す。
- **回帰試験**: 新規 `JevBlocklistTest`（2件）と、`AutofillProcessorTest` への1件（Unfillable 時に除外リストが Jev の provider に渡ること）。
  - `*Jev*Test` と `*AutofillProcessorTest` の結果は **38テスト、失敗0**。CodexのCollector修正と共存している。
- **detekt**: `JevFieldCollectorSecurityTest.kt` の26行目と53行目が MaxLineLength（100字）に違反している。Codexのファイルなので、こちらでは変更していない。
- APK を再ビルドして導入した。再導入で保管庫がロックされたため、端末での一括入力試験はユーザーによるロック解除待ち。ダミーの ID「Jev試験」はダミー値で作成・保存済み。

### 2026-09-28 Chrome拡張の担当
ユーザーの明示指定によりCodexが clients/ のChrome拡張実装を担当する。ClaudeはAndroidと端末試験を継続。プロフィールのカスタムフィールド名はAndroidの定義を共有し、既存の暗号化保管庫を再利用する。

### 2026-09-28 Codex: Chrome拡張の開発版を作成

担当分担はCodex=clients/のChrome拡張、Claude=android/の実装・端末検証を継続。双方が同じソースを編集しない。Chromeの概要・導入手順はCHROME.md、検証結果はVERIFICATION.md。

ChromeはIdentity+オリジン一致Loginの選択、全欄未承認の確認画面、選択欄だけの入力、任意のOpenRouter/Jev照会を実装。プロフィールのjev.*フィールド名はAndroidに合わせた。保管庫・暗号化方式は既存機構を再利用。ビルド/ESLint/33テスト成功、ZIP作成済み。Chrome実画面E2EとPC拡張からの実API通信は未検証。

トークン節約のためClaudeへ依頼する追加レビューは新規2ファイル（jev-page.ts、jev-policy.ts）だけに限定する予定だったが、非公開ソースのAnthropicへの外部送信について自動承認審査が許可不足として拒否。レビューは実行されていない。ユーザーに対象と宛先を明示して許可確認中。許可前に別経路で送らない。Macロック中のため既存Claude画面へ追加連絡も行っていない。本ファイルは引継ぎ記録であり、Claudeの受領・作業完了を意味しない。

### Claude限定レビュー実施（ユーザーの2ファイル送信許可後）

ユーザーが jev-page.ts / jev-policy.ts のAnthropicへの送信を明示許可したため、Claude Code safe-mode・ツールなし・1ターン・予算上限1.50 USDで実行。以前の「許可待ち」は解消済み。新規のレビュー用セッションでありAndroid担当セッションは変更していない。送信対象はこの2ファイルのみで、実認証情報や保管庫データは含めない。

Claudeは4件（視認性、郵便/電話の誤分割、住所の欠落、form属性のnamed-property clobbering）を報告。Codexが4件の失敗テストを再現して修正を担当。追加のClaude送信なし。ツール報告は1ターン、input 2 + cache creation 13175 + output 12028 tokens、推定API費用0.345968 USD（実請求額を示すものではない）。レビュー原文と機械的な使用量はGit管理外 `.build/claude-chrome-review.json`。Chromeでの実画面E2Eは依然未検証。

#### 2026-09-28 Claude: 端末E2E（途中経過）

- 修正版APKで combined.html を確認した。行ずれは解消し、選んだ行だけが入力される。全7欄の入力は `EXPECTED` どおり。詳細は VERIFICATION.md。
- 他のパターンページは、保管庫の再ロックと Chrome の ANR（ホスト負荷のため）で中断している。ブロックリストの端末試験（除外URIに登録して候補が出ないことの確認）も未実施。

#### 2026-09-28 Claude: 端末E2E完了

- 8ページすべてで一括入力を確認した（詳細の表は VERIFICATION.md）。
  - 未登録の部署・役職（era）と、郵便番号から住所を補完するページの上書き（autozip系の「入力」）を除き、期待どおりだった。
  - 「郵便番号以外を入力」では上書きを回避できる。
- ブロックリストの修正は端末でも確認した。`http://localhost` を除外すると Jev の候補も出ず、解除すると戻る。除外リストは空に戻してある。
- 未コミット（ユーザーの承認待ち）。`JevFieldCollectorSecurityTest.kt` の detekt MaxLineLength 2件は Codex 側で対応してほしい。

#### 2026-09-29 Claude: Chrome拡張のポップアップ起動が遅い件

- 原因: `scripts/build-chrome.py` が開発モード（`build:chrome`、`NODE_ENV` 未指定）でビルドしていた。圧縮されないため popup の JS が約24MBあり、同期境界の検出も有効になっていた。
- 変更: `build-chrome.py` で `NODE_ENV=production` を指定する1行だけ（Codex担当範囲のため最小限）。clients/ のソースは変更していない。
- 結果: popup の JS 約24MB→約6.9MB、background.js 9.7MB→3.3MB。ビルド時間は約15分。起動時間の実測はユーザーの再読み込み待ち。

#### 2026-09-29 Claude: PC拡張「入力欄を確認」が必ず失敗する不具合の修正（Codex担当ファイルを変更）

- **症状**: ユーザーが実機の Chrome（`https://localhost:8443` の fixture、自己署名証明書）で試すと、ID を選んで「入力欄を確認」を押しても毎回「準備できませんでした…」になった。
- **原因**: `jevPage` が `async` 関数だった。ビルド時に `return __awaiter(this, …)` へ変換され、`chrome.scripting.executeScript` は関数の本体だけをページへ送るため、ページ側で `ReferenceError: __awaiter is not defined` になっていた。Jest ではポップアップと同じモジュール内で直接呼ぶので、検出できていなかった。
- **修正**:
  - `jev-page.ts`: `jevPage` を非 async にした。入力後に1秒待つ処理は `setTimeout` を包む `Promise` を返す形に変更。
  - `browser-api.ts`: `executeFunctionInTab` の戻り値を `Awaited<R>` にした。
- **回帰試験**: `jev-page.spec.ts` に、`new Function` で関数の本体だけから作り直して実行する試験を追加した。修正前は `ReferenceError: __awaiter is not defined` で失敗することを確認した。
- **検証**:
  - Jev の3スイートは **38件成功**。
  - ESLint 成功。`apps/browser` の `tsc --noEmit` 成功。
  - `scripts/build-chrome.py` 終了0。ビルド後の `jevPage` に `__awaiter` がないことを確認した。
- **成果物**: ZIP の SHA256 は `c53999d53f22d4395394162327208fecc0641d8c3548bff0f7b3dcc49ba03057`（24,302,793 bytes）。前回の 28,201,720 bytes から減った理由は未確認。
- **未確認**: 修正後の Chrome 実機での一括入力は、ユーザーの再読み込み待ち。

#### 2026-09-29 Claude: PC拡張の一括入力UIを変更（ユーザーの要望）

- ユーザーの要望「欄ごとのチェックをやめ、見つけ次第すぐ入力してほしい」を受けて、`jev.component.ts` / `.html` を変更した。
  - Jev の画面を開いたとき、使う ID が分かっていれば（前回使った ID、または ID が1件だけ）即座に入力する。ID を選び直してもその場で入力し直す。
  - 入力するのは、判定できた空欄すべて。入力済みの欄は上書きしない。送信はしない。パスワードは、ログイン情報を選んだときだけ入る。
  - 前回使った ID は、popup の localStorage に項目IDだけを保存する。
  - 画面から「曖昧な欄をJevに照会」を外した（`classify()` はコードに残っている）。
- テスト: `quickFill` と、開いた瞬間の入力の2件を追加。Jev 3スイートで **40件成功**、ESLint・tsc 成功、`build-chrome.py` 終了0。
- ページを開いただけで入力する（ポップアップ操作なしの）自動入力は未実装。対象サイトの限定をユーザーと決めてから実装する。

#### 2026-09-29 Claude: PC拡張の判定を作り直し、Jev に実際の欄情報を渡すようにした

- **問題**: 旧 `jevPayload` が Jev に送っていたのは `{id, candidates}` だけで、欄名・記入例・name などを渡していなかった。しかも、端末ルールが候補を2つ以上出した欄しか問い合わせていなかった。Jev が毎回 UNKNOWN を返していたのは、判断材料がなかったため（Android/probe も同じ設計）。
- **ユーザーの承認**:
  - 欄名などページ側の文字を OpenRouter 経由で Jev に送ってよい。利用者の値、URL、パスワード欄は送らない。
  - APIキーは拡張の `chrome.storage.local` に保存してよい。
- **新規ファイル**（`clients/apps/browser/src/autofill/jev/`）:
  - `jev-kinds.ts`: Android の `JevFieldPolicy` の移植（種類のマスク、語彙、注記の除去、`localChoice`、`refine`）。
  - `jev-format.ts`: `JevFormat`、`JevFormatter`、`JevProfileMapper` の移植（書式の証拠、住所の組み立て、和暦、選択肢の一致）。
  - `jev-model.ts`: Jev への要求と答えの検証、および `planRows`。
    - 要求には、各欄のラベル・aria-label・直前の文字列・legend・placeholder・name・id・autocomplete・type・maxlength・選択肢を、各200字以内で入れる。同じ見出しで並ぶ欄には `splitPart` を付ける。
    - 問いのキーは `field_no_N`。ページの name（`f1` など）と衝突して答えがずれた実例があったため、この形にした。
    - 問い合わせるのは、端末ルールで UNKNOWN の欄だけ。1要求24問まで（大きいフォームは HTTP 400 になったため分割）。
    - 確信度0.6未満は使わない。複合住所の票は合計して `ADDRESS_FULL` とし、`refine` で他の欄が受け持つ部分を除く。
- **削除**: `jev-policy.ts` と `jev-policy.spec.ts`。観点は `jev-model.spec.ts` に移した。
- **ページ側**: `jev-page.ts` の欄情報に `caption`、`ariaLabel`、`placeholder`、`name`、`htmlId`、`context`（直前の文字列）、`group` を追加した。
- **ポップアップ**: 「Jev の設定」でキーを保存・削除できる。入力後の一覧で、Jev が判定した欄に［Jev］を付ける。キーがない、または通信に失敗したときは、端末ルールだけで入力する。
- **試験**:
  - Jev 4スイートで **48件成功**（合成ページ9枚を収集から値の組み立てまで照合する `jev-fixtures.spec.ts` を含む）。ESLint・tsc 成功。
  - 実フォームのコーパスの評価は `probe/corpus/eval/jev-eval.ts` で行った（esbuild でまとめて node で実行。キーは環境変数から読む）。
