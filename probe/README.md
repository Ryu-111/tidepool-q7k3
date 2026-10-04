# Android verification probe

**Not a product.** A standalone APK (Android SDK only, no Bitwarden) that checks form capture, bulk fill and Jev calls on Android with synthetic data. The classification and formatting rules here were later ported to `android/` and `clients/`.

## Build

```sh
rtk proxy python3 build.py
```

Needs Android SDK Platform 34, Build Tools 36.0.0 and JDK 21 (`ANDROID_HOME` / `JAVA_HOME` override the defaults). No downloads. Output: `.build/jev-probe.apk`, signed with a probe-only debug key. The build also runs the JVM policy tests (`test/dev/ryu/jevprobe/PolicyTest.java`).

## Manual check

1. Install the APK and pick it under "自動入力サービスを選択" (select autofill service).
2. "同梱のダミーフォームを開く" (open bundled form) → "自動入力候補を表示" (show suggestions) → "Jev 検証".
3. Choose "ローカル判定で確認" (local classification), select FAMILY / GIVEN / POSTAL / STREET / PASSWORD only (not the prefilled email), then "確認してダミー情報を一括入力".
4. "入力結果を検証" (verify) should show PASS. This is a native-form check, not proof of Chrome support.
5. For Chrome 135+, also select the external autofill service in Chrome settings and serve the web fixtures:

```sh
rtk proxy python3 -m http.server 8765 --bind 127.0.0.1 --directory fixture
rtk proxy adb reverse tcp:8765 tcp:8765
```

The probe only fills `com.android.chrome` / `http` / `localhost` and its own activity. This is a test-only restriction and is not a substitute for the product's HTTPS origin checks.

## Live Jev calls

Endpoint `https://openrouter.ai/api/v1/systemone`, model `jev-latest`, authenticated with an OpenRouter key ([OpenRouter System One API](https://openrouter.ai/docs/guides/community/typesafe-sdk)).

**From the Mac**: put exactly one line `OPENROUTER_API_KEY=<key>` (no quotes) in the root `.env`, mode 600, owned by you. Never paste the key into source, chat or shell commands. Then:

```sh
rtk proxy python3 probe/live_check.py
```

It sends one synthetic field, validates the reply, and prints only PASS/FAIL. It checks file mode, owner and links and rejects redirects.

**On Android**: enter a key on the main screen to keep it in memory for five minutes (never on disk, backup or logs). On the emulator, the key can be handed over from `.env` through a 30-second adb socket with a random name; only the adb UID is accepted and the option is hidden on physical devices.

```sh
PROBE_SERIAL=emulator-5556 PROBE_LIVE=1 rtk proxy python3 smoke.py   # add PROBE_CHROME=1 for the web form
```

Request rules: value-free field types only; labels are mapped to a fixed vocabulary (known notes such as "（必須）" are stripped first) and unknown text is dropped; password fields are classified on-device and never listed; only fields the local rules cannot decide (two or more candidates) are asked; replies are validated (field IDs, choices, probability distribution) and unknown or low-confidence answers stay unfilled.

## Fill patterns

`src/dev/ryu/jevprobe/Policy.java` decides field kinds; `Profile.java` formats values on-device.

- A kind is a set of address parts: region, municipality, ward, town, chome, ban, go, building. Parts handled by another field in the same form are removed from combined fields (e.g. with a region field, "住所" becomes `ADDRESS_AFTER_REGION`).
- Consecutive same-kind fields matching the number of parts are treated as split fields: postal 3+4, phone ×3, family/given name, kana ×2, municipality/ward, chome/ban/go, year/month/day. Mismatched counts and email confirmation fields are not split.
- Birth date: single field in several notations (`1990/04/05`, `19900405`, `1990年4月5日`, Japanese era), `type=date`, or year/month/day selects; separate era selects are supported. Gender and country: select or text (Chrome does not pass radio buttons). Age is computed on-device.
- Company, department and job title (text or select).
- Format (hyphens, full/half width, hiragana/katakana/half-width kana, name separators, `1丁目2番3号` style) comes from the label, placeholder and maxlength. Values that do not fit maxlength are not filled.
- Prefecture selects are matched against option text on-device; options are never sent to the model.
- Chrome's own hints (`ua-autofill-hints`) are used only when the page gives no hint of its own, because Chrome tends to mark the field before a password as `USERNAME`.

Synthetic pages live in `fixture/patterns/`:

| Page | Contents |
| --- | --- |
| `split.html` | Split name/kana, postal 3+4, prefecture select, phone ×3 |
| `combined.html` | Single name/kana/address fields, phone without hyphens, email + confirmation |
| `mixed.html` | Same-label split fields, address split from prefecture, phone format from placeholder |
| `profile.html` | Birth date selects, gender radio (must stay empty), age, country, municipality/ward/town/chome/ban/go |
| `variants.html` | 8-digit birth date, gender select, combined region/city, `type=date`, era date |
| `era.html` | Era + year selects, company, department, job title select |
| `ambiguous.html` | Name and label disagree; passes if filled as street or left empty |
| `autozip.html` / `autozipkey.html` | Postal-code autocompletion (reproduces the known conflict; currently FAIL) |

```sh
PROBE_SERIAL=emulator-5554 PROBE_CHROME=1 PROBE_PAGE=patterns/split.html rtk proxy python3 smoke.py
PROBE_SERIAL=emulator-5554 PROBE_CHROME=1 PROBE_PAGE=patterns/combined.html PROBE_FOCUS=お名前 rtk proxy python3 smoke.py
```

`PROBE_FOCUS` is the `<label>` text tapped first (default "姓"); use a text field, since a label wrapping a select opens the native picker. The dummy profile (Yokohama test address, 1990-04-05, etc.) is defined in `Profile.java` and is not real personal data.

## Limits

- Text fields, selects and native date fields only.
- Postal-code widgets rewrite the address about 0.3 s after the fill (Chrome also fires input/key events). Android fills all fields at once, so one pass cannot avoid it; "郵便番号以外を再入力" needs a second suggestion that did not appear reliably in automated runs.
- Android may hide existing values, so fields not known to be empty are not preselected; each needs explicit selection.
- Approval expires after 60 s or on a new autofill request.
- Do not keep the probe as your daily autofill service; restore the original service afterwards.
