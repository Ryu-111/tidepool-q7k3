# jev-autofill development rules (Claude Code / Codex)

Personal Bitwarden modification (Chrome extension and Android) that bulk-fills a Japanese profile and a site login. Product behavior: [README.md](README.md). Ownership and open issues: [COORDINATION.md](COORDINATION.md). Verified scope: [VERIFICATION.md](VERIFICATION.md). Chrome: [CHROME.md](CHROME.md). Probe: [probe/README.md](probe/README.md).

## Getting started

- Everything committed (docs, comments, identifiers, commit messages) is in English; use Conventional Commits. Japanese stays only where it is test data or matched UI text (form labels, fixtures, probe app strings).
- Read the "Rules" in README.md and the open issues in COORDINATION.md first.
- Run shell commands through `rtk`; use `rtk proxy <command>` when exact output or exit codes matter.

## Repository layout

| Path | Contents | Git |
| --- | --- | --- |
| `/` | Docs, `probe/`, `scripts/` | this repository |
| `android/` | Bitwarden Android; Jev code in `app/src/main/kotlin/com/x8bit/bitwarden/data/autofill/jev/` | separate working copy, `jev-autofill-prototype` |
| `clients/` | Bitwarden clients; Jev code in `apps/browser/src/autofill/jev/` and `apps/browser/src/autofill/popup/jev/` | separate working copy, `jev-autofill-prototype` |
| `sdk-internal/` | Official SDK `8b9fa3e2` for the local build | separate, do not edit |
| `reference/` | Community API samples; never ship | separate, do not edit |

- `android/` and `clients/` hold uncommitted work. Commit, stash, reset or switch branches there only when asked. They are ignored by the root repository, so run `git status` inside each.
- Keep upstream behavior intact (default arguments etc.) and add the Jev path alongside it.

## Ownership

- Follow the current ownership in COORDINATION.md. Edit the other agent's area only when the user asks.
- Record results at the end of COORDINATION.md; put verification details in VERIFICATION.md.
- Only one agent drives the emulator at a time.

## Jev request boundary (product requirement)

- Endpoint `https://openrouter.ai/api/v1/systemone`, model `jev-latest`, `choice` questions only. No fallback model. Keep redirect rejection, `credentials: "omit"`, a response size cap and a timeout.
- On-device rules first; ask only about fields they leave UNKNOWN; no request when there is nothing to ask. At most 24 questions per request. Question keys are `field_no_N` (never page names).
- Allowed: the page's own text about each field (label, aria-label, preceding text, legend, placeholder, name, id, autocomplete, type, maxlength, option labels), each clipped to 200 characters.
- **Never sent**: profile values, login data, the page URL, password fields, the API key (outside the auth header), page body, images, history. Never serialize `AutofillView.Data` or `CipherView`.
- Validate responses strictly; one malformed answer discards the whole reply. Ignore confidence below 0.6. Without a key or on failure, fill with on-device rules only.
- Filling requires an unlocked vault, a registered HTTPS origin match and re-validation right before filling. Skip hidden fields and cross-origin iframes. Never overwrite existing values silently. Never auto-submit. Never call OTP code (`totpManager`, clipboard). Apply the autofill blocklist (`JevBlocklist`) to Jev suggestions too.
- Extra profile data lives in encrypted custom fields; both clients share the `jev.*` keys in `JevCustomFieldKeys.kt`. No custom encryption, sync or SDK records.
- The probe's test-only allowances (`com.android.chrome` / `http` / `localhost`) must never reach product code.

## Secrets

- Never read, print or copy the root `.env` (`OPENROUTER_API_KEY=`, mode 600). Check connectivity with `rtk proxy python3 probe/live_check.py`, which prints neither the key nor the response body.
- Keep keys out of APKs, fixtures, logs, tests and docs. Use synthetic data only (e.g. the dummy identity "Jev試験"), never real vault data.
- Live OpenRouter calls cost money; run them only when the user asks. Unit tests use mocks or local servers.
- Do not read `*.jks`, `*.keystore` or `user.properties`.

## Commands

```sh
# probe (from the root)
rtk proxy python3 probe/build.py                          # JVM policy tests + APK
(cd probe && rtk proxy python3 -m unittest -v test_live_check.py test_emulator_key.py)
PROBE_SERIAL=emulator-5554 PROBE_CHROME=1 rtk proxy python3 probe/smoke.py   # device E2E (LOCAL)

# Android (in android/)
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME=$HOME/Library/Android/sdk \
  rtk proxy ./gradlew --offline --no-daemon --max-workers=2 -I ../scripts/local-sdk.init.gradle \
  :app:testStandardDebugUnitTest --tests '*Jev*Test'
# same environment for :app:detekt and :app:assembleStandardDebug

# Chrome extension (in clients/, with ../.tools/node-v24.17.0-darwin-arm64/bin first on PATH)
rtk proxy npx jest --config apps/browser/jest.config.js --runInBand apps/browser/src/autofill/jev apps/browser/src/autofill/popup/jev
rtk proxy npx eslint apps/browser/src/autofill/jev apps/browser/src/autofill/popup/jev
rtk proxy npx tsc --noEmit -p apps/browser/tsconfig.json
rtk proxy python3 ../scripts/build-chrome.py              # production build + ZIP (~15 min)
```

- Local SDK build: `rtk proxy python3 scripts/build-local-sdk.py` (no GitHub token).
- Stable emulator flags: `-gpu swiftshader_indirect -feature -Vulkan -no-window`. Afterwards stop the emulator and restore the autofill service.

## Known pitfalls

- The function passed to `chrome.scripting.executeScript` (`jevPage`) must not be `async`; the build turns it into `__awaiter` calls that fail in the page. Keep the `new Function` rebuild test in `jev-page.spec.ts`.
- `didAutofill` from `doAutoFill` means a fill was dispatched, not that it succeeded; E2E checks read DOM values.
- Chrome does not pass `<input type=radio>` to Android autofill. Postal-code widgets may rewrite address fields after a bulk fill.

## Verification and reporting

- Test the changed behavior and its failure paths before calling it done. Kotlin (detekt, Gradle) is not covered by hooks; run it manually.
- Keep these apart: unit test vs device E2E, LOCAL vs `JEV LIVE (no request)` vs a real Jev query, emulator vs physical device, localhost vs real HTTPS sites. State what is unverified.

## Development harness (jh / jev-router)

Global hooks from `jh` (`~/development/jev-router`) run in this repository too.

- PreToolUse(Agent): Jev picks the subagent model. UserPromptSubmit: may suggest a model switch.
- PostToolUse: formats edited files with Prettier (using `clients/` config). Stop: runs ESLint on edited TS/JS, then Jev judges completion and may send the turn back.
- These send the request (up to 8000 chars), the last reply (up to 4000 chars) and edited file names to Jev via OpenRouter, and keep text in `~/.jev/ledger` for 7 days. Never put secrets or vault data in prompts or replies.
- An empty `.jev-off` at the root stops all Jev traffic and logging; `JH_STOP_HOOK=off` disables only the Stop hook.
