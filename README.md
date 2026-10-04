# jev-autofill

[![probe](https://github.com/Ryu-111/tidepool-q7k3/actions/workflows/probe.yml/badge.svg)](https://github.com/Ryu-111/tidepool-q7k3/actions/workflows/probe.yml)
[![chrome](https://github.com/Ryu-111/tidepool-q7k3/actions/workflows/chrome.yml/badge.svg)](https://github.com/Ryu-111/tidepool-q7k3/actions/workflows/chrome.yml)
[![annotator](https://github.com/Ryu-111/tidepool-q7k3/actions/workflows/annotator.yml/badge.svg)](https://github.com/Ryu-111/tidepool-q7k3/actions/workflows/annotator.yml)

Personal modification of Bitwarden (Chrome extension and Android app) that fills a Japanese personal profile and a site login into a web form in one step. Fields the on-device rules cannot classify are optionally sent to Jev (via OpenRouter) as value-free field descriptions. Submission is always manual.

## Status

Prototype. Not for general use.

- **Chrome extension**: builds and passes unit tests; real-page use in Chrome is only partly verified.
- **Android**: integrated into Bitwarden debug builds; end-to-end fill verified on an emulator against local test pages only.
- Details: [VERIFICATION.md](VERIFICATION.md). Open issues and ownership: [COORDINATION.md](COORDINATION.md).

## Layout

| Path | Contents |
| --- | --- |
| `probe/` | Standalone Android verification app, synthetic test forms, policy tests, E2E scripts ([probe/README.md](probe/README.md)) |
| `scripts/` | Local Bitwarden SDK build, Gradle init script, Chrome extension build and patch export |
| `clients-patch/` | The Chrome extension changes as a patch on a pinned bitwarden/clients commit; CI builds the extension from it |
| `annotator/` | Local web app for labelling the real-form corpus and scoring classifiers ([annotator/README.md](annotator/README.md)) |
| `android/`, `clients/` | Upstream Bitwarden working copies on branch `jev-autofill-prototype` (not in this repository) |

## Rules

- No profile value, login, page URL, password field or API key ever goes into a model request.
- The existing Bitwarden vault, encryption and sync are reused; extra profile fields are encrypted custom fields (`jev.*`).
- Filling requires an unlocked vault, a matching HTTPS origin and re-validated fields; existing values are never overwritten silently; nothing is auto-submitted.

Architecture: [docs/architecture.md](docs/architecture.md). Contributor rules: [AGENTS.md](AGENTS.md). Chrome usage: [CHROME.md](CHROME.md).

## Out of scope

Auto-submit, multi-page flows, payment cards, OTP, passkeys, password generation.
