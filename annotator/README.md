# jev-annotator

Local web app for labelling the field kinds of the real-form corpus (`probe/corpus/raw/`), so the
classifiers' error rate can be measured against ground truth.

The corpus and the labels are third-party page structure and stay local: labels are written to
`probe/corpus/labels/labels.json` (ignored by Git). The server binds to `127.0.0.1` only.

## Run

```sh
cd annotator/web && npm ci && npm run build && cd ..
uv run jev-annotator                 # opens http://127.0.0.1:8790/
```

Options: `--corpus <dir>` (default `../probe/corpus`), `--pages <list>` (default
`eval/usable.txt`), `--labels <file>`, `serve --port <n> --no-browser`.

Add Chrome extension correction exports with `--feedback <file.json>` before the subcommand:

```sh
uv run jev-annotator --feedback corrections.json
```

Each fill appears as a `feedback/<fill>` page, with the recorded decision and subsequent user
action shown beside each field. Labels use the same store as corpus labels. The corpus is still
required. Only version 1 exports are accepted; malformed outcomes are skipped and counted.

## Labelling

Each fillable control (hidden, button, checkbox and radio controls are left out, as in
`eval/jev-eval.ts`) gets one kind. The kinds mirror `KIND_MASKS` in the Chrome extension's
`jev-kinds.ts`; `OTHER` means "not a profile field, leave it empty".

| Key | Action |
| --- | --- |
| `j` / `k` | Next / previous field |
| `/`, then Enter | Filter kinds, assign the first match and move on |
| `o` | `OTHER` and move on |
| `.` | Same kind as the previous field and move on |
| `u` / `n` / `x` | Toggle unsure / edit note / clear |
| `d` | Mark the page finished |
| `[` / `]` | Previous / next page |

A label whose field changed after re-collection is flagged "欄が変更された".

## Scoring classifiers

```sh
uv run jev-annotator report ../probe/corpus/eval/all-before.tsv   # CorpusEval (probe Policy)
uv run jev-annotator report <jev-eval output>.tsv                 # columns local / jev / final
uv run jev-annotator report-feedback corrections.json           # recorded extension decisions
```

Counts `correct`, `wrong` (another profile value would be filled), `missed` (left empty) and
`spurious` (a non-profile field filled). Unsure labels are excluded.
`report-feedback` also lists labelled fields and differing decisions for each user action
(`kept`, `edited`, `cleared`, `typed`); an edit need not mean a classification error.

## Checks

`./check.sh` runs Ruff (all rules), Mypy (strict), pytest (branch coverage ≥ 85%), tsc (strict)
and ESLint (`strictTypeChecked`, no HTML sinks, complexity limits).
