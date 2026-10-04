package dev.ryu.jevprobe;

import android.app.PendingIntent;
import android.app.assist.AssistStructure;
import android.content.Intent;
import android.os.CancellationSignal;
import android.os.SystemClock;
import android.service.autofill.*;
import android.text.InputType;
import android.view.View;
import android.view.autofill.AutofillId;
import android.widget.RemoteViews;
import java.util.*;

/** Isolated capability probe: can fill only bundled synthetic forms / localhost in Chrome. */
public final class ProbeService extends AutofillService {
    static volatile Pending pending;
    static final class Target {
        final AutofillId androidId;
        final Policy.Field field;
        final boolean emptyKnown;
        // Device-local only: never serialized into a model request.
        final Profile.Format format;
        final CharSequence[] options;
        final int autofillType;
        Target(AutofillId id, Policy.Field field, boolean emptyKnown, Profile.Format format,
               CharSequence[] options, int autofillType) {
            this.androidId = id; this.field = field; this.emptyKnown = emptyKnown;
            this.format = format; this.options = options; this.autofillType = autofillType;
        }
    }
    static final class Pending {
        final String token = UUID.randomUUID().toString();
        final long expires = SystemClock.elapsedRealtime() + 60000;
        final List<Target> targets;
        final String source;
        Pending(List<Target> targets, String source) { this.targets = targets; this.source = source; }
        boolean valid(String token) {
            return pending == this && this.token.equals(token)
                && SystemClock.elapsedRealtime() < expires;
        }
    }
    @Override public void onFillRequest(FillRequest request, CancellationSignal cancellation,
                                       FillCallback callback) {
        pending = null;
        if (request.getFillContexts().isEmpty() || cancellation.isCanceled()) {
            callback.onSuccess(null); return;
        }
        AssistStructure structure = request.getFillContexts()
            .get(request.getFillContexts().size() - 1).getStructure();
        String pkg = structure.getActivityComponent().getPackageName();
        boolean fixture = pkg.equals(getPackageName()) && structure.getActivityComponent()
            .getClassName().equals(FixtureActivity.class.getName());
        if (!fixture && !pkg.equals("com.android.chrome")) { callback.onSuccess(null); return; }
        List<Target> targets = new ArrayList<>();
        for (int i = 0; i < structure.getWindowNodeCount(); i++) {
            collect(structure.getWindowNodeAt(i).getRootViewNode(), pkg, fixture, null, null,
                targets, new int[]{0});
        }
        if (targets.isEmpty() || targets.size() > 32) { callback.onSuccess(null); return; }
        Pending current = new Pending(targets, fixture ? "同梱のダミーフォーム" : "Chrome / localhost");
        pending = current;
        cancellation.setOnCancelListener(() -> { if (pending == current) pending = null; });
        Intent intent = new Intent(this, ConfirmActivity.class).putExtra("token", current.token);
        PendingIntent auth = PendingIntent.getActivity(this, current.token.hashCode(), intent,
            PendingIntent.FLAG_CANCEL_CURRENT | PendingIntent.FLAG_MUTABLE);
        AutofillId[] ids = new AutofillId[targets.size()];
        for (int i = 0; i < ids.length; i++) ids[i] = targets.get(i).androidId;
        RemoteViews menu = new RemoteViews(getPackageName(), android.R.layout.simple_list_item_1);
        menu.setTextViewText(android.R.id.text1, "Jev 検証: ダミー情報を一括入力");
        callback.onSuccess(new FillResponse.Builder().setAuthentication(ids, auth.getIntentSender(), menu).build());
    }
    private static void collect(AssistStructure.ViewNode node, String pkg, boolean fixture,
                                String domain, String scheme, List<Target> targets, int[] visited) {
        if (++visited[0] > 2048 || targets.size() > 32) return;
        if (node.getWebDomain() != null) {
            domain = node.getWebDomain();
            scheme = node.getWebScheme();
        }
        boolean trusted = fixture || Policy.allowedTarget(pkg, scheme, domain);
        CharSequence value = node.getAutofillValue() != null && node.getAutofillValue().isText()
            ? node.getAutofillValue().getTextValue() : node.getText();
        boolean list = node.getAutofillType() == View.AUTOFILL_TYPE_LIST
            && node.getAutofillOptions() != null && node.getAutofillOptions().length <= 128;
        boolean toggle = node.getAutofillType() == View.AUTOFILL_TYPE_TOGGLE;
        boolean date = node.getAutofillType() == View.AUTOFILL_TYPE_DATE;
        if (trusted && node.getAutofillId() != null && node.isEnabled()
            && node.getVisibility() == View.VISIBLE
            && (list || toggle || date || node.getAutofillType() == View.AUTOFILL_TYPE_TEXT
                && (value == null || value.length() == 0))) {
            Set<Policy.Kind> hints = EnumSet.noneOf(Policy.Kind.class);
            Set<Policy.Kind> browserGuesses = EnumSet.noneOf(Policy.Kind.class);
            List<String> formatTexts = new ArrayList<>();
            String caption = null;  // a radio button's own label, e.g. 女性
            Policy.Shape shape = list ? Policy.Shape.LIST : toggle ? Policy.Shape.TOGGLE
                : date ? Policy.Shape.DATE : shape(node.getInputType());
            boolean fixedShape = list || toggle || date;
            int maxLength = node.getMaxTextLength();
            if (node.getAutofillHints() != null) {
                for (String hint : node.getAutofillHints()) hints.add(Policy.label(hint));
            }
            hints.add(Policy.label(node.getHint()));
            if (node.getHint() != null) formatTexts.add(node.getHint().toString());
            if (node.getHtmlInfo() != null && node.getHtmlInfo().getAttributes() != null) {
                for (android.util.Pair<String, String> attribute : node.getHtmlInfo().getAttributes()) {
                    String key = attribute.first, text = attribute.second;
                    if (key == null || text == null) continue;
                    if ("type".equals(key) && !fixedShape) {
                        if ("password".equals(text)) shape = Policy.Shape.PASSWORD;
                        if ("number".equals(text)) shape = Policy.Shape.NUMBER;
                        // A text-typed <input type=date> still takes an HTML date string.
                        if ("date".equals(text)) shape = Policy.Shape.DATE;
                    }
                    if ("label".equals(key) && toggle) caption = text;
                    if ("maxlength".equals(key) && text.matches("[0-9]{1,4}"))
                        maxLength = Integer.parseInt(text);
                    if (Arrays.asList("placeholder", "aria-label", "label", "name", "id").contains(key))
                        hints.add(Policy.label(text));
                    if (Arrays.asList("placeholder", "aria-label", "label").contains(key))
                        formatTexts.add(text);
                    // Token lists. Chrome forwards the author's autocomplete as HTML_TYPE_* inside
                    // computed-autofill-hints; everything else there is Chrome's own guess.
                    if (Arrays.asList("autocomplete", "ua-autofill-hints", "crowdsourcing-autofill-hints",
                        "computed-autofill-hints").contains(key) && text.length() <= 256) {
                        for (String token : text.split("[\\s,]+")) {
                            boolean author = "autocomplete".equals(key) || token.startsWith("HTML_TYPE_");
                            (author ? hints : browserGuesses).add(Policy.label(token));
                        }
                    }
                }
            }
            // Browser heuristics only fill gaps. They must not override page evidence: Chrome's
            // password heuristics label the field before a password box USERNAME even when the
            // page says 番地 / address-line1.
            hints.remove(Policy.Kind.UNKNOWN);
            if (hints.isEmpty()) hints.addAll(browserGuesses);
            // A redacted value is UNKNOWN, not proof that a field is empty. Unknown occupancy
            // must receive individual, explicit approval in ConfirmActivity.
            boolean emptyKnown = !list && node.getAutofillValue() != null
                && node.getAutofillValue().isText()
                && node.getAutofillValue().getTextValue().length() == 0;
            if (android.util.Log.isLoggable("JevProbe", android.util.Log.DEBUG)) {
                // Value-free diagnostics: attribute names and resolved kinds only, never raw text.
                StringBuilder trace = new StringBuilder("field " + targets.size() + " " + shape + hints);
                if (node.getHtmlInfo() != null && node.getHtmlInfo().getAttributes() != null) {
                    for (android.util.Pair<String, String> a : node.getHtmlInfo().getAttributes())
                        trace.append(' ').append(a.first).append('=').append(a.second == null ? "-"
                            : a.first.endsWith("hints") ? a.second.replaceAll("[^A-Z_,]", "")
                            : Policy.label(a.second).name());
                }
                android.util.Log.d("JevProbe", trace.toString());
            }
            Profile.Format format = Profile.Format.parse(formatTexts, maxLength);
            if (toggle && caption == null) caption = node.getText() != null ? node.getText().toString()
                : node.getContentDescription() != null ? node.getContentDescription().toString() : null;
            CharSequence[] options = list ? node.getAutofillOptions()
                : toggle ? new CharSequence[]{caption} : null;
            int id = Math.min(targets.size(), 31);
            targets.add(new Target(node.getAutofillId(), new Policy.Field(id, shape, hints),
                emptyKnown, format, options, node.getAutofillType()));
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            collect(node.getChildAt(i), pkg, fixture, domain, scheme, targets, visited);
        }
    }
    private static Policy.Shape shape(int inputType) {
        int variation = inputType & InputType.TYPE_MASK_VARIATION;
        if (variation == InputType.TYPE_TEXT_VARIATION_PASSWORD
            || variation == InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD) return Policy.Shape.PASSWORD;
        if ((inputType & InputType.TYPE_MASK_CLASS) == InputType.TYPE_CLASS_PHONE) return Policy.Shape.TEL;
        if ((inputType & InputType.TYPE_MASK_CLASS) == InputType.TYPE_CLASS_NUMBER) return Policy.Shape.NUMBER;
        if (variation == InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
            || variation == InputType.TYPE_TEXT_VARIATION_WEB_EMAIL_ADDRESS) return Policy.Shape.EMAIL;
        return Policy.Shape.TEXT;
    }
    @Override public void onSaveRequest(SaveRequest request, SaveCallback callback) {
        // No capture, disk storage or vault emulation in the probe.
        callback.onSuccess();
    }
}
