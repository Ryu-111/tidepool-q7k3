// Corpus evaluation of the PC extension's classifier: on-device rules, then Jev for the rest.
// Build: esbuild probe/corpus/eval/jev-eval.ts --bundle --platform=node --format=esm --outfile=…
// Run:   node <bundle> <out.tsv> <raw json>...   (reads OPENROUTER_API_KEY from the environment)
import { readFileSync, writeFileSync } from "node:fs";

import { localKind, askJev, planRows } from "../../../clients/apps/browser/src/autofill/jev/jev-model";
import type { JevPageField } from "../../../clients/apps/browser/src/autofill/jev/jev-page";

interface RawField {
  tag: string;
  type?: string;
  name?: string;
  id?: string;
  placeholder?: string;
  autocomplete?: string;
  maxlength?: string;
  label?: string;
  near?: string[];
  legend?: string;
  options?: string[];
  title?: string;
}

const skip = new Set(["hidden", "submit", "button", "reset", "image", "file", "checkbox", "radio"]);
const toFields = (raw: RawField[]): JevPageField[] =>
  raw
    .filter((f) => !skip.has(f.type ?? ""))
    .map((f, id) => ({
      id,
      type: f.tag === "select" ? "select" : f.tag === "textarea" ? "textarea" : f.type || "text",
      labels: [],
      caption: f.label ?? "",
      ariaLabel: f.title ?? "",
      placeholder: f.placeholder ?? "",
      name: f.name ?? "",
      htmlId: f.id ?? "",
      context: (f.near ?? []).join(" "),
      group: f.legend ?? "",
      autocomplete: f.autocomplete ?? "",
      maxLength: Number(f.maxlength) > 0 ? Number(f.maxlength) : -1,
      options: (f.options ?? []).map((o) => ({ value: o, label: o })),
      occupied: false,
    }));

const key = process.env.OPENROUTER_API_KEY ?? "";
const [out, ...files] = process.argv.slice(2);
const lines = ["page\tform\tno\tlocal\tjev\tconf\tfinal\tsource\ttype\tlabel\tcontext\tname\tplaceholder"];
let jevCalls = 0;
let jevFailures = 0;
for (const file of files) {
  const page = JSON.parse(readFileSync(file, "utf8")) as { forms: { fields: RawField[] }[] };
  for (const [formIndex, form] of page.forms.entries()) {
    const fields = toFields(form.fields);
    if (!fields.length) {
      continue;
    }
    const local = fields.map(localKind);
    let jev: Awaited<ReturnType<typeof askJev>> = {};
    if (key && local.some((k, i) => k === "UNKNOWN" && fields[i].type !== "password")) {
      jevCalls++;
      try {
        jev = await askJev(fields, key, AbortSignal.timeout(90_000));
      } catch (e) {
        jevFailures++;
        process.stderr.write(`Jev failed for ${file}#${formIndex}: ${String(e).slice(0, 120)}\n`);
      }
    }
    // A dummy profile only so every kind renders; the classification is what is measured.
    const rows = planRows(fields, {}, jev);
    rows.forEach((row, i) => {
      const f = fields[i];
      const clean = (s: string) => s.replace(/[\t\n]/g, " ").slice(0, 60);
      lines.push(
        [
          file.replace(/^.*raw\//, ""),
          formIndex,
          f.id,
          local[i],
          jev[f.id]?.kind ?? "",
          jev[f.id]?.confidence.toFixed(2) ?? "",
          row.kind,
          row.source,
          f.type,
          clean(f.caption),
          clean(f.context),
          clean(f.name),
          clean(f.placeholder),
        ].join("\t"),
      );
    });
  }
}
writeFileSync(out, lines.join("\n") + "\n");
process.stderr.write(`forms asked Jev: ${jevCalls}, failures: ${jevFailures}\n`);
