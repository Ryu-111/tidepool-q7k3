package dev.ryu.jevprobe;

import android.app.Activity;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.view.autofill.AutofillManager;
import android.widget.*;
import java.util.*;

public final class FixtureActivity extends Activity {
    static String dummy(Policy.Kind kind) {
        return Profile.render(kind, Profile.Format.DEFAULT, Policy.Shape.TEXT);
    }
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        LinearLayout box = MainActivity.layout(this);
        MainActivity.text(this, box, "同梱フォーム（Chromeの実証とは別です）");
        Map<Policy.Kind, EditText> fields = new LinkedHashMap<>();
        String[] hints = {"family-name", "given-name", "postal-code", "address-line1", "current-password"};
        Policy.Kind[] kinds = {Policy.Kind.FAMILY, Policy.Kind.GIVEN, Policy.Kind.POSTAL,
            Policy.Kind.STREET, Policy.Kind.PASSWORD};
        for (int i = 0; i < kinds.length; i++) {
            EditText field = new EditText(this);
            field.setId(View.generateViewId()); field.setHint(hints[i]); field.setAutofillHints(hints[i]);
            field.setInputType(InputType.TYPE_CLASS_TEXT | (kinds[i] == Policy.Kind.PASSWORD
                ? InputType.TYPE_TEXT_VARIATION_PASSWORD : InputType.TYPE_TEXT_VARIATION_NORMAL));
            box.addView(field); fields.put(kinds[i], field);
        }
        EditText existing = new EditText(this);
        existing.setHint("email"); existing.setText("do-not-overwrite@example.invalid"); box.addView(existing);
        EditText hidden = new EditText(this);
        hidden.setHint("email"); hidden.setVisibility(View.GONE); box.addView(hidden);
        TextView result = MainActivity.text(this, box, "未検証");
        MainActivity.button(this, box, "自動入力候補を表示", () -> {
            EditText first = fields.get(Policy.Kind.FAMILY);
            first.requestFocus(); getSystemService(AutofillManager.class).requestAutofill(first);
        });
        MainActivity.button(this, box, "入力結果を検証", () -> {
            boolean ok = true;
            for (Map.Entry<Policy.Kind, EditText> field : fields.entrySet())
                ok &= dummy(field.getKey()).equals(field.getValue().getText().toString());
            ok &= "do-not-overwrite@example.invalid".equals(existing.getText().toString());
            ok &= hidden.getText().length() == 0;
            result.setText(ok ? "PASS: 5項目一括入力・既存値保持・非表示欄未入力" : "FAIL: 入力は未完了");
            android.util.Log.i("JevProbeTest", ok ? "fixture PASS" : "fixture FAIL");
        });
    }
}
