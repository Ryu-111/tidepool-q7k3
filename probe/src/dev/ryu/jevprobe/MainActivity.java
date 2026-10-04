package dev.ryu.jevprobe;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.text.InputType;
import android.view.*;
import android.widget.*;

public final class MainActivity extends Activity {
    private static String apiKey;
    private static long expires;
    static synchronized boolean setKey(String value) {
        if (value == null || value.isEmpty() || value.length() > 4096
            || !value.matches("[!-~]+") || value.contains("\"") || value.contains("'")) return false;
        apiKey = value;
        expires = SystemClock.elapsedRealtime() + 300000;
        new Handler(Looper.getMainLooper()).postDelayed(MainActivity::activeKey, 300001);
        return true;
    }
    static synchronized String activeKey() {
        if (SystemClock.elapsedRealtime() > expires) apiKey = null;
        return apiKey;
    }
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        LinearLayout box = layout(this);
        text(this, box, "Jev Android 検証用\n実際の保管庫・秘密情報は扱いません。\n"
            + "入力対象は同梱フォームとChromeのlocalhostのみ。\n"
            + "通常のHTTPSサイトでは動かない試作です。");
        text(this, box, "自己テスト: " + JsonSelfTest.run());
        EditText key = new EditText(this);
        key.setHint("OpenRouter APIキー（任意・保存なし）");
        key.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        key.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        key.setSaveEnabled(false);
        box.addView(key);
        TextView status = text(this, box, "APIキー未設定でもローカル検証できます。");
        button(this, box, "APIキーをメモリに設定（5分）", () -> {
            if (!setKey(key.getText().toString().trim())) {
                status.setText("APIキーの形式を確認してください。設定は変更していません。");
                return;
            }
            key.setText("");
            status.setText("メモリに設定しました。ファイルには保存していません。");
        });
        if ("ranchu".equals(Build.HARDWARE)) {
            button(this, box, "エミュレーター専用: Macからキーを受信", () -> {
                status.setText("30秒間だけ受信待機します。");
                new Thread(() -> {
                    boolean ok = EmulatorKey.receive(name -> runOnUiThread(
                        () -> status.setText("受信待機中: " + name)));
                    runOnUiThread(() -> status.setText(ok
                        ? "受信完了: キーを5分間メモリに設定しました。"
                        : "キー受信失敗: 再試行してください。"));
                }).start();
            });
        }
        button(this, box, "キーを破棄・試作をロック", () -> {
            synchronized (MainActivity.class) { apiKey = null; expires = 0; }
            ProbeService.pending = null;
            status.setText("キーを破棄しました。");
        });
        button(this, box, "自動入力サービスを選択", () -> startActivity(
            new Intent(Settings.ACTION_REQUEST_SET_AUTOFILL_SERVICE,
                Uri.parse("package:" + getPackageName()))));
        button(this, box, "Chromeの自動入力設定", () -> {
            try {
                startActivity(new Intent(Intent.ACTION_APPLICATION_PREFERENCES)
                    .addCategory(Intent.CATEGORY_DEFAULT)
                    .addCategory(Intent.CATEGORY_APP_BROWSER)
                    .addCategory(Intent.CATEGORY_PREFERENCE).setPackage("com.android.chrome"));
            } catch (android.content.ActivityNotFoundException missing) {
                status.setText("対応するChromeが見つかりません。");
            }
        });
        button(this, box, "同梱のダミーフォームを開く", () -> startActivity(new Intent(this, FixtureActivity.class)));
        button(this, box, "Chromeのダミーフォームを開く", () -> startActivity(
            new Intent(Intent.ACTION_VIEW, Uri.parse("http://localhost:8765/"))
                .setPackage("com.android.chrome")));
    }
    static LinearLayout layout(Activity activity) {
        ScrollView scroll = new ScrollView(activity);
        LinearLayout layout = new LinearLayout(activity);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(24, 24, 24, 24);
        scroll.addView(layout);
        activity.setContentView(scroll);
        return layout;
    }
    static TextView text(Activity activity, LinearLayout box, String content) {
        TextView view = new TextView(activity);
        view.setText(content); view.setTextSize(16); box.addView(view); return view;
    }
    static void button(Activity activity, LinearLayout box, String label, Runnable action) {
        Button button = new Button(activity);
        button.setText(label); button.setOnClickListener(view -> action.run()); box.addView(button);
    }
}
