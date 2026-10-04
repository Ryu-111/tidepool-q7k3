# Jevフォーム一括入力

個人用のBitwarden改修プロジェクトです。**Chrome拡張の開発版を実装しました。ビルド・自動テストまで確認済みで、Chromeに読み込んでの保管庫・フォーム通し試験は未確認です。** AndroidはClaudeが実装を担当しています。

Chrome拡張の導入・操作・再ビルド手順は [CHROME.md](CHROME.md)、最新の検証範囲は [VERIFICATION.md](VERIFICATION.md) を参照してください。

## 現在の成果物

- `probe/`: Android SDKのみでビルドできる検証アプリ、ローカルWebフォーム、入力ポリシー試験、Android UIスモーク試験。
- `android/`: 公式Bitwarden Androidの取得済み作業コピー。`jev-autofill-prototype` ブランチ。保管庫・暗号化・同期を再利用し、Identity一括入力の製品組み込みをClaudeが担当。最新状況は `COORDINATION.md` を参照。
- `clients/`: 公式Bitwardenクライアントの取得済み作業コピー。`jev-autofill-prototype` ブランチ。プロフィールとサイト別ログインを確認後に一括入力する開発版を実装。OpenRouter/Jevへの任意照会、保管庫ロック・ページ変更・既存値の再検証を含む。
- `sdk-internal/`: Androidが要求するコミット `8b9fa3e2672633a2170116cc9fe66f7637850839` の公式SDK。GitHubトークンを使わず手元でビルドするために取得。
- `scripts/build-local-sdk.py`: SDKのARM64向けローカルビルド手順。`scripts/local-sdk.init.gradle` はAndroidビルドでGitHub Packagesを参照せず、この成果物へ切り替えるための設定。
- `reference/typesafe-playground/`: APIの補助資料として取得したコミュニティサンプル。公式製品ではなく、コードは製品へ組み込んでいません。

2026-09-26にOpenRouter経由へ切り替えました。[公式互換API](https://openrouter.ai/docs/guides/community/typesafe-sdk) の `https://openrouter.ai/api/v1/systemone` / `jev-latest` / `choice` を使います。OpenRouterがJevへ転送し、別モデルへの自動フォールバックは行いません。同日、Macからの実API通信に成功し、Android 16でも同梱ダミーフォームを対象にJev実通信・5項目一括入力・既存値保持・非表示欄未入力を確認しました。同日、Android 17エミュレーターのChrome 145でも、localhostのダミーWebフォームに対してJev実通信と一括入力のE2Eが成功しました（HTTPS実サイトは未確認）。

ビルドと使い方は [probe/README.md](probe/README.md) を参照してください。

MacからのAPI接続確認用キーは、Git管理外の `.env` の `OPENROUTER_API_KEY=` に設定します（権限600）。`rtk proxy python3 probe/live_check.py` で実値を出力せずに確認できます。APKへは埋め込みません。

## 合意した製品の動作

PCはBitwarden Chrome拡張、AndroidはBitwarden Androidアプリを個人用に改修します。現在のChromeフォームに、本人プロフィールとサイト別ログイン情報を確認後まとめて入力します。送信は手動です。

プロフィールは姓・名・フリガナ・郵便番号・都道府県・市区町村・番地・建物名・電話番号・メール。ログイン情報はユーザー名とパスワードです。Bitwardenの既存保管庫と暗号化同期を再利用し、独自の暗号化・同期プロトコルは作りません。

ローカル判定を優先し、不明な欄だけJevへ照会します。Jevへ送信できるのは一時的な欄ID・入力型・配置関係・固定語彙に正規化したラベルだけです。パスワードだけでなく氏名・住所の実値、APIキー、URL、本文、画像、履歴もモデルの要求には入れません。OpenRouterのAPIキーは通信の認証ヘッダーにのみ必要です。

実際の入力は端末が行います。入力前に保管庫の解錠、登録済みHTTPSオリジンの照合、欄の再検証、本人の確認を必須にします。不正応答・不明欄・非表示欄・別オリジンのiframeは拒否し、既存値を無断で上書きしません。

先行試験で、Androidが既存値を伏せることを確認しました。値が取得できない欄は空欄とみなさず初期選択を外し、項目ごとの明示選択でのみ置換を許可します。Androidでの完全自動の空欄判定は未解決です。

## Androidを先に検証する理由

合意した計画では、Android Chrome上で欄情報の取得、住所とパスワードの一括入力、Jev呼び出しが成立することが本実装の開始条件です。同梱ネイティブフォームの成功やモック応答だけでは、この条件を満たしたと扱いません。

初回（2026-09-24）に確認した開発環境:

- 接続された実機なし。既存エミュレーターはAndroid 14 / Chrome 113.0.5672.136。
- Chromeの新しい外部自動入力方式は135以降が対象。113での成功を新方式の検証結果へ置き換えません。
- シェル環境に `TYPESAFE_API_KEY`、`GITHUB_TOKEN`、`GH_TOKEN` の設定なし（値は調べていません）。
- Bitwarden Androidの取得時HEADは `bf85c77ff5c9a18b8450adab6640921713ff1386`。READMEはJDK 21とGitHub Packages `read:packages`用トークン、Gradle設定はSDK 37を要求。ローカルSDKは36まで、Bitwarden SDKのキャッシュなし。
- JDK 21とAndroid SDK 34 / Build Tools 36は利用できたため、検証APKは依存取得なしでビルド可能。

2026-09-25更新: SDK Platform 37.0とAndroid 16のGoogle APIs ARM64イメージを導入し、専用AVD `Jev_API_36` を作成しました。起動・APKインストール・Android上のJSON自己テストは成功。ただし同梱Chromeは133.0.6943.137で、Chrome 135以降の検証条件は未達です。

## 本実装の再開条件

1. Android Chrome 135以降の検証先を用意する。既存の実機設定変更・実データ移行は本人の操作と区別する。2026-09-26、Android 17エミュレーター（Chrome 145.0.7632.218、emulator 37.3.1）で達成。実機は未確認。
2. OpenRouter APIキーを試作の入力画面に設定し、合成データのみで `JEV LIVE` の結果を確認する。キーはチャット・Git・ログへ貼らない。2026-09-26、ネイティブフォームとChromeのダミーWebフォームの両方で達成。
3. Bitwardenのビルド要件を満たす。2026-09-26のユーザー指定により、GitHubトークンは使わず公式SDKのローカルビルドを採用する。2026-09-26にSDKのローカルビルド、Bitwarden Android（standardDebug, ARM64）のビルド、Android 16での起動とSDK初期化まで確認済み。ログイン・同期・自動入力は未確認。
4. 先行検証が通ったら、下記の改修へ進む。通らなければ原因と制約を報告し、未検証のまま一般サイトへの入力を有効にしない。

## Bitwardenへの組み込み箇所

取得したAndroidソースの `data/autofill` には既にIdentityの分類がありますが、Loginとは別のPartitionです。`parser/AutofillParserImpl.kt` → `processor/AutofillProcessorImpl.kt` → 選択／完了処理を追い、プロフィールとLoginの選択を同じ確認フローにまとめる必要があります。

改修では単に自動入力サービスを追加して併用するのではなく、Bitwardenのサービス内に統合します。モデルへの要求には既存の `AutofillView.Data` を直接シリアライズしてはいけません。これは `textValue` と `website` を持っています。値を持たない専用データへ変換する境界が必要です。

Chrome拡張側も同じ値なし要求・検証規則を使います。Content ScriptからAPIキーや全保管庫にアクセスさせず、必要な入力値だけを入力直前に渡します。Chrome開発版のパスワード取得・オリジン照合は拡張の保管庫画面で行い、ページ側へは明示承認された入力値だけを渡します。

API停止時のローカル判定、入力直前のページ変更、ロック、端末間同期、競合、バックアップ復元まで検証してから、個人用の拡張と署名済みAndroidアプリを配布します。

## 初版に含めない機能

自動送信、複数ページ巡回、カード情報、OTP、パスキー、新規パスワード生成。取得できない独自フォーム部品は手動入力として表示します。全サイトでの完全自動入力を保証しません。
