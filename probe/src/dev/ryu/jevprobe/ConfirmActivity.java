package dev.ryu.jevprobe;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.service.autofill.*;
import android.view.WindowManager;
import android.view.autofill.*;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;

public final class ConfirmActivity extends Activity {
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private ProbeService.Pending current;
    private String token;
    private LinearLayout layout;
    private TextView status;
    private List<Policy.Field> fields;
    private Map<Integer, Policy.Kind> choices;
    private final Set<Integer> approved = new HashSet<>();
    private final Set<Integer> fromJev = new HashSet<>();
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        setResult(RESULT_CANCELED);
        token = getIntent().getStringExtra("token");
        current = ProbeService.pending;
        if (current == null || !current.valid(token)) { finish(); return; }
        layout = MainActivity.layout(this);
        status = MainActivity.text(this, layout, "検証用・実際の個人情報は使いません\n" + current.source);
        fields = new ArrayList<>();
        choices = new HashMap<>();
        for (ProbeService.Target target : current.targets) {
            fields.add(target.field);
            choices.put(target.field.id, target.field.localChoice());
        }
        MainActivity.button(this, layout, "ローカル判定で確認（Jev通信なし）", () -> review("LOCAL"));
        MainActivity.button(this, layout, "Jevで判定する（APIを1回呼び出す）", this::classify);
        MainActivity.button(this, layout, "キャンセル", this::finish);
    }
    private void classify() {
        String key = MainActivity.activeKey();
        if (key == null) { status.setText("メイン画面でAPIキーを設定してください。未送信です。"); return; }
        if (!current.valid(token)) { finish(); return; }
        // Local rules first (agreed design): only fields they cannot resolve are asked, and
        // only when the page offers at least two candidate kinds for the model to choose from.
        List<Policy.Field> unresolved = new ArrayList<>();
        for (Policy.Field field : fields)
            if (field.localChoice() == Policy.Kind.UNKNOWN && field.choices().size() >= 2) unresolved.add(field);
        if (unresolved.isEmpty()) { review("JEV LIVE（照会対象なし・全欄ローカル判定、通信なし）"); return; }
        layout.removeAllViews();
        status = MainActivity.text(this, layout, "Jevへ送信中：" + unresolved.size()
            + "欄の種類と正規化した分類候補のみ");
        MainActivity.button(this, layout, "キャンセル", this::finish);
        worker.submit(() -> {
            try {
                Map<Integer, Policy.Kind> result = Jev.request(fields, unresolved, key);
                runOnUiThread(() -> {
                    if (isFinishing() || !current.valid(token)) return;
                    // Each field shows where its kind came from; a failed Jev answer stays UNKNOWN.
                    for (Policy.Field field : unresolved) {
                        Policy.Kind kind = result.getOrDefault(field.id, Policy.Kind.UNKNOWN);
                        choices.put(field.id, kind);
                        if (kind != Policy.Kind.UNKNOWN) fromJev.add(field.id);
                    }
                    review("JEV LIVE（" + unresolved.size() + "欄を照会、Jev判定 " + fromJev.size() + "欄）");
                });
            } catch (Exception failure) {
                runOnUiThread(() -> {
                    if (!isFinishing()) status.setText("Jev判定に失敗しました。入力は実行していません。");
                });
            }
        });
    }
    private void review(String mode) {
        if (!current.valid(token)) { finish(); return; }
        layout.removeAllViews();
        approved.clear();
        // Split fields and combined addresses are resolved from kinds and order, on-device.
        choices = Policy.refine(fields, choices);
        MainActivity.text(this, layout, mode + " / " + current.source
            + "\nOSが既存値を伏せる欄があります。空欄とは限りません。\n"
            + "入力する欄だけ選択してください。選択した欄の既存値は置き換わります。");
        Button fillButton = new Button(this);
        fillButton.setText("確認してダミー情報を一括入力");
        fillButton.setEnabled(false);
        fillButton.setOnClickListener(view -> fill(false));
        // Zip-to-address widgets rewrite the address fields after a batch fill that includes the
        // postal code (Chrome fires input and key events while filling). A second pass without
        // the postal code restores the address without re-triggering the widget.
        boolean postal = false, address = false;
        for (Policy.Kind kind : choices.values()) {
            postal |= kind.within(Policy.Kind.POSTAL);
            address |= (kind.mask & 0xFF) != 0;
        }
        Button refillButton = postal && address ? new Button(this) : null;
        if (refillButton != null) {
            MainActivity.text(this, layout, "郵便番号から住所を自動補完するページでは、入力後に住所欄が"
                + "書き換わることがあります。その場合はもう一度この画面を開き「郵便番号以外を再入力」を押してください。");
            refillButton.setText("郵便番号以外を再入力");
            refillButton.setOnClickListener(view -> fill(true));
        }
        for (ProbeService.Target target : current.targets) {
            Policy.Kind kind = choices.getOrDefault(target.field.id, Policy.Kind.UNKNOWN);
            AutofillValue value = kind == Policy.Kind.UNKNOWN ? null : value(target, kind);
            // Of a radio group only the matching button is shown; the others are not touched.
            if (target.field.shape == Policy.Shape.TOGGLE && value == null) continue;
            String preview = value == null ? null : kind == Policy.Kind.PASSWORD ? "（パスワード）"
                : value.isList() ? String.valueOf(target.options[value.getListValue()])
                : value.isToggle() ? "選択: " + target.options[0]
                : value.isDate() ? "日付: " + Profile.BIRTH : String.valueOf(value.getTextValue());
            CheckBox check = new CheckBox(this);
            check.setText((fromJev.contains(target.field.id) ? "［Jev］" : "")
                + "欄 " + target.field.id + ": " + kind.name()
                + (preview == null ? "" : " → " + preview)
                + (kind != Policy.Kind.UNKNOWN && value == null ? "（形式・文字数が合わないため入力しない）"
                    : target.emptyKnown ? "（空欄確認済み）" : "（既存値は不明・選択で置換に同意）"));
            check.setEnabled(value != null);
            if (value != null && target.emptyKnown) {
                approved.add(target.field.id); check.setChecked(true);
            }
            check.setOnCheckedChangeListener((view, checked) -> {
                if (checked) approved.add(target.field.id); else approved.remove(target.field.id);
                fillButton.setEnabled(!approved.isEmpty());
                if (refillButton != null) refillButton.setEnabled(!approved.isEmpty());
            });
            layout.addView(check);
        }
        fillButton.setEnabled(!approved.isEmpty());
        layout.addView(fillButton);
        if (refillButton != null) {
            refillButton.setEnabled(!approved.isEmpty());
            layout.addView(refillButton);
        }
        MainActivity.button(this, layout, "キャンセル", this::finish);
    }
    private void fill(boolean skipPostal) {
        if (!current.valid(token)) { finish(); return; }
        RemoteViews menu = new RemoteViews(getPackageName(), android.R.layout.simple_list_item_1);
        menu.setTextViewText(android.R.id.text1, "ダミー情報");
        Dataset.Builder dataset = new Dataset.Builder(menu);
        int count = 0;
        for (ProbeService.Target target : current.targets) {
            if (!approved.contains(target.field.id)) continue;
            Policy.Kind kind = choices.getOrDefault(target.field.id, Policy.Kind.UNKNOWN);
            if (skipPostal && kind.within(Policy.Kind.POSTAL)) continue;
            AutofillValue value = value(target, kind);
            if (value != null && target.field.compatible(kind)) {
                dataset.setValue(target.androidId, value); count++;
            }
        }
        if (count == 0) { finish(); return; }
        FillResponse response = new FillResponse.Builder().addDataset(dataset.build()).build();
        setResult(RESULT_OK, new Intent().putExtra(AutofillManager.EXTRA_AUTHENTICATION_RESULT, response));
        ProbeService.pending = null;
        finish();
    }
    private static AutofillValue value(ProbeService.Target target, Policy.Kind kind) {
        if (kind == Policy.Kind.UNKNOWN || !target.field.compatible(kind)) return null;
        if (target.field.shape == Policy.Shape.LIST) {
            int index = Profile.optionIndex(target.options, kind);
            return index < 0 ? null : AutofillValue.forList(index);
        }
        if (target.field.shape == Policy.Shape.TOGGLE) {
            return target.options != null && Profile.toggleMatches(target.options[0], kind)
                ? AutofillValue.forToggle(true) : null;
        }
        if (target.autofillType == android.view.View.AUTOFILL_TYPE_DATE)
            return AutofillValue.forDate(Profile.birthMillis());
        String text = Profile.render(kind, target.format, target.field.shape);
        return text == null ? null : AutofillValue.forText(text);
    }
    @Override public void onDestroy() {
        worker.shutdownNow();
        if (ProbeService.pending == current) ProbeService.pending = null;
        super.onDestroy();
    }
}
