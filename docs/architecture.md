# Architecture

How jev-autofill fits into Bitwarden and where the trust boundaries are. Rules behind these choices: [AGENTS.md](../AGENTS.md#jev-request-boundary-product-requirement).

## Overview

```mermaid
flowchart LR
  subgraph device["User device"]
    vault[("Bitwarden vault<br/>Identity + Login<br/>jev.* custom fields<br/>(existing encryption and sync)")]
    subgraph chrome["Chrome extension (clients/)"]
      popup["Popup<br/>jev.component"]
      model["jev-model / jev-kinds / jev-format<br/>classify, plan, render"]
      page["jevPage<br/>(injected via executeScript)"]
    end
    subgraph android["Android app (android/)"]
      processor["AutofillProcessorImpl<br/>+ JevBulkFillEntry"]
      collector["JevFieldCollector<br/>JevFieldPolicy"]
      completion["MainActivity →<br/>JevBulkFillCompletion<br/>planner + formatter"]
    end
    form["Web form<br/>(HTTPS page)"]
  end
  jev["Jev<br/>OpenRouter /api/v1/systemone<br/>model jev-latest"]

  vault --> popup
  vault --> completion
  popup <--> page
  page <--> form
  popup --> model
  model -. "UNKNOWN fields only:<br/>page text about fields" .-> jev
  form -- "AssistStructure" --> processor
  processor --> collector
  processor --> completion
  completion -- "one Dataset" --> form
```

- Both clients share the same design: **on-device rules first**, Jev only for fields the rules leave UNKNOWN, and **every value is rendered on the device**. Jev returns a field kind, never a value.
- Profile data stays in the existing Bitwarden vault (Identity plus encrypted `jev.*` custom fields). There is no separate store, encryption or sync.
- Today only the Chrome extension queries Jev; Android uses on-device rules only (porting the request format is an open issue).

## Trust boundary

```mermaid
flowchart LR
  subgraph local["Never leaves the device"]
    values["Profile values, login, password"]
    url["Page URL, body, history"]
    key["API key (except the auth header)"]
  end
  subgraph sent["May be sent to Jev"]
    text["Per field: label, aria-label, preceding text,<br/>legend, placeholder, name, id, autocomplete,<br/>type, maxlength, option labels (≤200 chars)"]
    ids["Temporary keys field_no_N"]
  end
  sent --> jev["Jev via OpenRouter"]
  jev --> answer["kind + confidence<br/>(validated; &lt;0.6 ignored)"]
```

Before any value is written: vault unlocked, HTTPS origin matches, fields re-validated, hidden fields and cross-origin iframes skipped, existing values kept, no auto-submit, no OTP, blocklist applied.

## Chrome extension flow

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant P as Popup (jev.component)
  participant V as Vault service
  participant S as jevPage (in tab)
  participant M as jev-model
  participant J as Jev (OpenRouter)
  U->>P: Open "Jev" on an HTTPS tab
  P->>V: Unlocked? Identity, logins matching the origin
  P->>S: Collect visible fields (no values sent out)
  S-->>P: Field descriptions
  P->>M: localKind per field
  alt UNKNOWN fields and a saved key
    M->>J: Field text, ≤24 questions per request
    J-->>M: kind + confidence
  else no key or failure
    M->>M: On-device rules only
  end
  M-->>P: Plan rows with rendered values
  P->>S: Fill approved rows (re-check origin, visibility, type, value)
  S-->>P: Filled / skipped, changes after 1 s
  P-->>U: Result list ([Jev] marks Jev-classified fields)
```

Code: `clients/apps/browser/src/autofill/jev/` (`jev-page.ts`, `jev-model.ts`, `jev-kinds.ts`, `jev-format.ts`) and `clients/apps/browser/src/autofill/popup/jev/`.

## Android flow

```mermaid
sequenceDiagram
  autonumber
  participant C as Chrome / app
  participant A as AutofillProcessorImpl
  participant E as JevBulkFillEntry
  participant K as JevFieldCollector
  participant M as MainActivity
  participant B as JevBulkFillCompletion
  participant V as Vault
  C->>A: FillRequest (AssistStructure)
  A->>E: Build Jev suggestion (blocklist check)
  E->>K: Collect fields (HTTPS / same-origin, hidden subtrees and >2048 nodes rejected)
  E-->>A: "Jev" dataset (placeholder values)
  A-->>C: FillResponse (regular datasets unchanged)
  C->>M: User taps the Jev suggestion
  M->>V: Existing unlock / re-prompt flow, pick Identity
  M->>B: complete(selection, blocklist)
  B->>B: Plan + format on-device, confirmation dialog
  B-->>C: One Dataset with approved fields only
```

Code: `android/app/src/main/kotlin/com/x8bit/bitwarden/data/autofill/jev/`. Existing classes changed only through defaulted parameters: `AutofillSelectionData`, `AutofillIntentUtils`, `FillResponseBuilder(Impl)`, `AutofillProcessorImpl`, `MainActivity`, `InlinePresentationSpecExtensions`.

## Shared classification model

- A field kind is a bit mask of profile parts (name, kana, postal, address parts region → building, phone parts, birth date parts, gender, company, …). Combined fields are unions, e.g. `ADDRESS_FULL`.
- `refine` removes parts that other fields in the same form already cover and splits consecutive same-label fields (postal 3+4, phone ×3, …).
- Formatting (hyphens, width, kana type, era dates) comes from the field's label, placeholder and maxlength.
- Origin of the rules: `probe/src/dev/ryu/jevprobe/Policy.java` and `Profile.java`, ported to Kotlin (`JevFieldPolicy`, `JevFormatter`) and TypeScript (`jev-kinds.ts`, `jev-format.ts`).

## Verification layers

| Layer | Where | Runs in CI |
| --- | --- | --- |
| Policy rules (JVM, 164 assertions) | `probe/test/` | yes (`.github/workflows/probe.yml`) |
| Probe Python tools (key handling, transport) | `probe/test_*.py` | yes |
| Android unit tests, detekt | `android/` | no (separate working copy) |
| Chrome Jest, ESLint, tsc | `clients/` | no (separate working copy) |
| Device E2E on synthetic pages | `probe/smoke.py`, `probe/fixture/patterns/` | no (emulator) |
| Real-form evaluation | `probe/corpus/` (data kept local) | no |
