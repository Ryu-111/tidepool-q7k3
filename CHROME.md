# Chrome extension (personal development build)

Modified Bitwarden OSS browser extension. It reuses the existing encrypted vault and adds no password storage of its own. Not published to the Chrome Web Store.

## Install

1. Build: `rtk proxy python3 scripts/build-chrome.py` (Node 24.17+ and npm 11; dependencies from `npm ci --ignore-scripts` in `clients/`; the build prefers the Node runtime in `.tools/`). Output: `chrome-dist/jev-autofill-chrome/` and `chrome-dist/jev-autofill-chrome.zip`.
2. In `chrome://extensions`, enable Developer mode and load `chrome-dist/jev-autofill-chrome/` unpacked. It has its own name and ID, separate from the store extension.
3. Log in to a test vault and prepare an Identity (and optionally a login for the site).

## Use

1. Open an HTTPS form and choose "Jev" from the extension's vault screen.
2. If the identity is known (the last one used, or the only one), the extension fills immediately; choosing another identity refills.
3. It fills every empty field it can classify. Filled fields are never overwritten. The password is filled only when a login is selected. Nothing is submitted.
4. Review the "filled" / "not filled" lists and submit the form yourself.

Fields are re-validated right before filling (page, frame, HTTPS origin, visibility, type, current value). Only fields visible on screen are targeted; tiny, transparent, clipped or covered fields are skipped, so scroll and reopen for long forms. Changes by postal-code widgets are detected about one second after filling and are not re-filled automatically.

Passwords require an exact HTTPS origin match (scheme, host, port); Exact/StartsWith URI rules still apply, Never and regex matching are not used, and items with password re-prompt go through the existing re-prompt.

## Jev / OpenRouter

- Optional. Save an OpenRouter key under "Jev settings"; it is kept in this extension's `chrome.storage.local` only. Without a key, or on any failure, only the on-device rules are used.
- Only fields the on-device rules leave UNKNOWN are sent, as the page's own text about each field (label, aria-label, preceding text, legend, placeholder, name, id, autocomplete, type, maxlength, option labels). Profile values, the URL and password fields are never sent.
- Fields classified by Jev are marked [Jev] in the result list.

## Profile fields

Standard name, address, phone and email come from the Bitwarden Identity. Extra fields are custom fields shared with Android:

`jev.family_kana`, `jev.given_kana`, `jev.municipality`, `jev.ward`, `jev.town`, `jev.chome`, `jev.ban`, `jev.go`, `jev.birthdate` (YYYY-MM-DD), `jev.gender` (female/male/other), `jev.department`, `jev.job_title`

Missing data is never guessed.

## Not supported

HTTP pages, other frames, radio buttons, Shadow DOM, custom widgets, filling on page load without opening the popup.
