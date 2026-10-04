# Real-form structure corpus

Tools for collecting the **value-free structure** of public Japanese sign-up and application forms, to measure how the fill rules cope with real forms beyond the synthetic pages in `fixture/patterns/`.

The collected data (`raw/`, `excluded/`, `index.tsv`, `eval/*.tsv`, `eval/usable.txt`) is third-party page structure and is kept local only (see `.gitignore`).

## Data format

`raw/<category>/*.json`: one page per file. Per field: tag, type, name, id, placeholder, autocomplete, maxlength, required, label (`<label>` text), near (three preceding text nodes), legend, select option labels. **No input values, hidden fields or form targets are stored.**

## Tools

| File | Role |
| --- | --- |
| `extract_form.py <html> <url> <category>` | Writes the value-free structure JSON of one HTML page (standard library only) |
| `render.sh <url> <out.html>` | One GET in headless Chrome with a throwaway profile; saves the DOM after scripts run |
| `profile_score.py <json>...` | Counts profile-like fields; 4+ counts as usable |
| `collect.sh <category> <url>` | robots.txt check → static fetch → render if needed → follow one form-like link → extract, score, log. Skips non-200 and not-found pages; never retries a URL. Set `H=` inside for the HTML cache directory |
| `eval/to_tsv.py <json>...` | Flattens JSON into an approximation of the hints Chrome passes to Android |
| `../test/dev/ryu/jevprobe/CorpusEval.java` | Classifies that TSV with the probe `Policy` |
| `eval/jev-eval.ts` | Evaluates the Chrome extension classifier, optionally with Jev (key from the environment) |

Re-run the on-device baseline (in `probe/corpus/`):

```sh
J="/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin"
"$J/javac" -nowarn --release 8 -encoding UTF-8 -d ../.build/eval ../src/dev/ryu/jevprobe/Policy.java ../src/dev/ryu/jevprobe/Profile.java ../test/dev/ryu/jevprobe/CorpusEval.java
python3 eval/to_tsv.py $(cat eval/usable.txt) | "$J/java" -cp ../.build/eval dev.ryu.jevprobe.CorpusEval > eval/all-before.tsv
```

## Results so far (2026-09-29)

98 usable pages from 95 sites, 156 forms, about 2,000 fields.

- Probe rules only: 354 of 805 profile-like fields (43%) were UNKNOWN; 11 of 156 forms exceeded the 32-field limit. Main causes: hints only in name/id, labels outside the vocabulary, examples used as labels, unbracketed "必須" notes.
- Chrome extension classifier: on-device rules 449 fields, Jev 552 more; no failed requests after splitting into 24 questions per request. Spot checks after tightening the "only the user's own data" instruction: 1 clear error in 50 random fields.
- Limits: labels are approximated; there are no ground-truth labels, so the error rate is not formally measured.

## Next steps

1. Re-measure with the hints Chrome actually passes (serve saved pages locally, log with `setprop log.tag.JevProbe DEBUG`).
2. Add ground-truth labels for a sample to measure misclassification.
3. Port the improvements to Android.
