# Coordination (Claude / Codex)

Current ownership, integration notes and open issues. Append new entries at the end; do not edit the same section concurrently. The full handoff log up to 2026-09-29 is in Git history (`f3c0679:COORDINATION.md`).

## Ownership

- **Claude**: `android/` product code, emulator E2E, `probe/`.
- **Codex**: `clients/` Chrome extension (Claude has also changed it at the user's request; see the log in history).
- Edit the other side's area only when the user asks, and record it here.

## Integration notes

### Android

- `AutofillParserImpl` picks only Login or Identity per focus; the Jev path uses its own collector (`JevFieldCollector`) and planner instead of changing the parser or partitions.
- Approved fields go into one Dataset; no Cipher is synthesized or saved.
- Vault unlock and re-prompt go through the existing selection flow; results are discarded on lock or account switch.
- The bulk-fill path never calls `totpManager`.
- `JevBlocklist` applies the built-in and user blocklists (and rejects unknown URIs) before suggestions and again before filling.
- `JevFieldCollector` excludes hidden subtrees and rejects the whole form above 2,048 nodes.

### Chrome extension

- Call `doAutoFill` with `allowUntrustedIframe: false`, `autoSubmitLogin: false`, `fillNewPassword: false`, `allowTotpAutofill: false`; do not reuse the single-item defaults.
- Re-check tab, document/frame, HTTPS origin, visibility, type and current value right before filling.
- Read form attributes via `Element.prototype` to avoid named-property clobbering.

### Storage

Standard name, address, phone and email use the Bitwarden Identity. Extra data uses encrypted custom fields with keys from `JevCustomFieldKeys.kt`: `jev.family_kana`, `jev.given_kana`, `jev.municipality`, `jev.ward`, `jev.town`, `jev.chome`, `jev.ban`, `jev.go`, `jev.birthdate` (ISO date), `jev.gender` (female/male/other), `jev.department`, `jev.job_title`. Addresses are stored as confirmed by the user, never split by guesswork.

## Open issues

1. Port the Chrome extension's Jev request format (page field text, `field_no_N`, 24-question chunks) to Android; Android does not query Jev yet.
2. Android: fill login and profile in one approval.
3. Postal-code autocompletion conflict on Android.
4. Chrome: real-browser E2E with Jev and a real vault; decide whether to fill on page load for selected sites.
5. Ground-truth labels for the corpus to measure misclassification.
6. `JevFieldCollectorSecurityTest.kt` has two detekt MaxLineLength violations (lines 26 and 53).
7. Physical device and real HTTPS sites are untested; release signing and distribution are not done.

## Log

- 2026-10-04 Claude: repository published; docs translated to English and condensed.
- 2026-10-04 Claude + Codex: added `annotator/` (corpus labelling and scoring; 464 fields labelled so far), Chrome correction-feedback recording (`chrome.storage.local`, no values), `clients-patch/` with the `chrome` CI/CD workflow, and git flow branches. Codex implemented the feedback import and the review fixes; Claude integrated and verified. Unverified: feedback recording in a real Chrome.
- 2026-10-06 Claude + Codex: Chrome rules now use row headings, sections (other people / workplace), neighbors, width/kana notes and `pattern`; new kinds MOBILE/MOBILE_1..3 and custom field `jev.mobile_phone`. Android still lacks the `jev.mobile_phone` key in `JevCustomFieldKeys.kt` and the MOBILE kinds. `probe/corpus/eval/jev-eval-dom.ts` evaluates on rendered snapshots.
