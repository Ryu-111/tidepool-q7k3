# Verification

What has been verified, and how. The full dated log up to 2026-09-29 is in Git history (`f3c0679:VERIFICATION.md`).

Environment: Android 17 emulator `Jev_API_37` with Chrome 145.0.7632.218 (emulator 37.3.1), local fixtures on `http://localhost:8765`. No physical device, no real HTTPS site.

## Summary

| Area | Verified | Not verified |
| --- | --- | --- |
| Jev API | Mac → OpenRouter live call with a synthetic field (`probe/live_check.py`); Android probe live call | — |
| Probe (Android) | JVM policy tests (164); Python tests (6); Chrome E2E on 8 pattern pages, LOCAL and JEV LIVE | Physical device, HTTPS sites |
| Bitwarden Android | 38 Jev/processor unit tests, detekt; emulator E2E with a logged-in test vault on all pattern pages; blocklist fix on device | Jev query in the product path, login + profile fill together, release signing |
| Chrome extension | 48 Jest tests (4 suites incl. 9 synthetic pages end to end), ESLint, tsc, production build | Real Chrome UI end to end with Jev, sync and recovery with a real vault |
| Real-form corpus | Classifier evaluation on 98 pages (see `probe/corpus/README.md`) | Ground-truth error rate |

## Bitwarden Android E2E (2026-09-28)

Dummy identity "Jev試験" (standard fields plus `jev.*` custom fields, all synthetic); every row approved, values compared with each page's `EXPECTED` via CDP.

| Page | Result | Notes |
| --- | --- | --- |
| combined | 7/7 | Also verified first/last-row-only selection after the row-offset fix |
| split | 13/13 | |
| mixed | 10/10 | |
| profile | 14/14 | Gender radio stays empty, as expected |
| variants | 8/8 | `type=date` via `AUTOFILL_TYPE_DATE` |
| era | 6/8 | Department and job title not in the test identity, left empty |
| ambiguous | 4/4 | Undecidable field left empty |
| autozip / autozipkey | 5/6 | Page script overwrites the address after the fill (known conflict); "fill all but postal code" avoids it |

Blocklist: with `http://localhost` blocked, every request returned `Unfillable` and no Jev suggestion appeared; removing it restored filling.

## Jev quality

- Probe: Jev was queried only on `ambiguous.html`; both answers were UNKNOWN or low confidence (safe, but no field was filled by Jev).
- Chrome extension (2026-09-29): sending the page's own field text instead of bare candidates lets Jev classify many fields the rules cannot (corpus figures in `probe/corpus/README.md`). Latency 0.4–5 s per request.

## Known issues

- Chrome does not pass radio buttons to Android autofill.
- Postal-code widgets overwrite address fields after an Android bulk fill; the "fill all but postal code" second pass does not appear reliably.
- Android may mask existing values, so emptiness cannot always be confirmed; such fields need explicit approval.
- Emulator: Chrome may crash on Vulkan init; use `-gpu swiftshader_indirect -feature -Vulkan -no-window`. Under host load Chrome may ANR.

## Commands

See [AGENTS.md](AGENTS.md#commands).
