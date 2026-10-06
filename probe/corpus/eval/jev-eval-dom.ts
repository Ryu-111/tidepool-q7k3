// Offline DOM evaluation; no page scripts, remote resources, or Jev requests are executed.
// Run these commands:
// export PATH="/Users/ryu/development/jev-autofill/.tools/node-v24.17.0-darwin-arm64/bin:$PATH"
// cd /Users/ryu/development/jev-autofill
// clients/node_modules/.bin/esbuild probe/corpus/eval/jev-eval-dom.ts --bundle --platform=node --format=esm --outfile=/tmp/jev-eval-dom.mjs --external:jsdom --log-level=warning
// (cd probe/corpus && NODE_PATH=/Users/ryu/development/jev-autofill/clients/node_modules node /tmp/jev-eval-dom.mjs eval/dom-now.tsv $(cat eval/usable.txt))
// cd /Users/ryu/development/jev-autofill/.claude/worktrees/annotation-webapp-linting-1fd696/annotator
// uv run jev-annotator --pages eval/split-dev.txt report /Users/ryu/development/jev-autofill/probe/corpus/eval/dom-now.tsv
// Repeat the report with eval/split-test.txt. Self-check: node /tmp/jev-eval-dom.mjs --self-test
import assert from "node:assert/strict";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve, sep } from "node:path";

import {
  localKind,
  planRows,
} from "../../../clients/apps/browser/src/autofill/jev/jev-model";
import { jevPage } from "../../../clients/apps/browser/src/autofill/jev/jev-page";

// ESM ignores NODE_PATH; CommonJS resolution honors the documented run command.
const { JSDOM, VirtualConsole } = createRequire(import.meta.url)(
  "jsdom",
) as typeof import("jsdom");
type Control = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
interface RawField {
  tag: string;
  type?: string;
  name?: string;
  id?: string;
}
interface Page {
  source_url: string;
  forms: { fields: RawField[] }[];
}
interface Coordinate {
  form: number;
  no: number;
}
const extractionSkip = new Set([
  "hidden",
  "submit",
  "button",
  "reset",
  "image",
  "file",
]);
const reportSkip = new Set([...extractionSkip, "checkbox", "radio"]);
const controlType = (node: Element) =>
  node.localName === "input"
    ? (node.getAttribute("type") ?? "text").toLowerCase()
    : node.localName;
const sameText = (actual: string | null, recorded = "") =>
  (actual ?? "").replace(/\s+/g, " ").trim().startsWith(recorded);

function coordinates(doc: Document, page: Page) {
  const byForm = new Map<Element, Control[]>();
  const outside: Control[] = [];
  for (const node of doc.querySelectorAll<Control>("input, select, textarea")) {
    if (extractionSkip.has(controlType(node))) continue;
    const form = node.closest("form");
    if (!form) outside.push(node);
    else {
      const controls = byForm.get(form) ?? [];
      controls.push(node);
      byForm.set(form, controls);
    }
  }
  const groups = [...doc.querySelectorAll("form")].flatMap((form) => {
    const controls = byForm.get(form);
    return controls ? [controls] : [];
  });
  if (outside.length) groups.push(outside);
  const mapped = new Map<Control, Coordinate>();
  groups.forEach((controls, form) => {
    // TSV uses the filtered index, while matching uses the original raw position.
    const raw = page.forms[form]?.fields ?? [];
    const numbers = new Map<number, number>();
    let no = 0;
    raw.forEach((field, index) => {
      if (!reportSkip.has(field.type ?? "")) numbers.set(index, no++);
    });
    controls.forEach((node, index) => {
      const field = raw[index];
      const number = numbers.get(index);
      if (
        field &&
        number !== undefined &&
        node.localName === field.tag &&
        controlType(node) === (field.type ?? field.tag) &&
        sameText(node.getAttribute("name"), field.name) &&
        sameText(node.id, field.id)
      ) {
        mapped.set(node, { form, no: number });
      }
    });
  });
  return mapped;
}

async function evaluate(html: string, page: Page) {
  // CSS parsing diagnostics contain entire stylesheets and are irrelevant to mocked layout.
  const dom = new JSDOM(html, {
    url: page.source_url,
    runScripts: "outside-only",
    virtualConsole: new VirtualConsole(),
  });
  const win = dom.window;
  try {
    const controls = [
      ...win.document.querySelectorAll<Control>("input, select, textarea"),
    ];
    const positions = new Map(controls.map((node, index) => [node, index]));
    // jsdom has no layout: synthetic non-overlapping rectangles make every control
    // hit-testable, including long forms. Semantic hidden/disabled checks remain real.
    Object.defineProperty(win, "innerHeight", {
      value: Math.max(768, controls.length * 30 + 40),
    });
    win.HTMLElement.prototype.getClientRects = function () {
      const top = 10 + (positions.get(this as Control) ?? 0) * 30;
      return [
        { width: 100, height: 20, left: 10, top, right: 110, bottom: top + 20 },
      ] as unknown as DOMRectList;
    };
    win.getComputedStyle = () =>
      ({
        display: "block",
        visibility: "visible",
        opacity: "1",
        clipPath: "none",
        clip: "auto",
      }) as CSSStyleDeclaration;
    win.document.elementFromPoint = (_x, y) =>
      controls[Math.floor((y - 10) / 30)] ?? null;
    Object.defineProperty(win.crypto, "randomUUID", {
      value: () => "corpus-evaluation",
    });
    const collect = new win.Function(
      `return (${jevPage.toString()})`,
    )() as typeof jevPage;
    const result = await collect({ action: "collect", url: win.location.href });
    if (!result) return null;
    // The collector's own snapshot retains the exact elements for its sequential ids;
    // duplicate name/id attributes therefore cannot map a result to the wrong control.
    const state = (
      win as unknown as { __jevBulkFill: { nodes: { node: Control }[] } }
    ).__jevBulkFill;
    assert.equal(state.nodes.length, result.fields.length);
    const mapped = coordinates(win.document, page);
    const rows = planRows(result.fields, {}, {});
    let mismatches = 0;
    const lines: string[] = [];
    const clean = (s: string) => s.replace(/[\t\r\n]/g, " ").slice(0, 60);
    rows.forEach((row, i) => {
      const field = result.fields[i];
      assert.equal(field.id, i);
      const coordinate = mapped.get(state.nodes[field.id].node);
      if (!coordinate) {
        mismatches++;
        return;
      }
      lines.push(
        [
          coordinate.form,
          coordinate.no,
          localKind(field),
          "",
          "",
          row.kind,
          row.source,
          field.type,
          clean(field.caption),
          clean(field.context),
          clean(field.name),
          clean(field.placeholder),
        ].join("\t"),
      );
    });
    return { lines, mismatches };
  } finally {
    win.close(); // Also cancels the collector's two-minute expiry timer.
  }
}

async function selfTest() {
  const html =
    '<input name="outside"><form><input type="hidden"></form>' +
    '<form><input type="radio"><label>姓<input name="family" id="family-long"></label>' +
    '<input hidden name="hidden"><input disabled name="disabled"><input readonly name="readonly">' +
    '<label>メール<input type="email" name="email"></label></form>';
  const page: Page = {
    source_url: "https://example.test/form",
    forms: [
      {
        fields: [
          { tag: "input", type: "radio" },
          { tag: "input", type: "text", name: "family", id: "family-" },
          ...["hidden", "disabled", "readonly"].map((name) => ({
            tag: "input",
            type: "text",
            name,
          })),
          { tag: "input", type: "email", name: "email" },
        ],
      },
      { fields: [{ tag: "input", type: "text", name: "outside" }] },
    ],
  };
  const result = await evaluate(html, page);
  assert.equal(result?.mismatches, 0);
  assert.deepEqual(
    result?.lines.map((line) => line.split("\t").slice(0, 2)),
    [
      ["1", "0"],
      ["0", "0"],
      ["0", "4"],
    ],
  );
  assert.equal(result?.lines[1].split("\t")[5], "FAMILY");
  page.forms[0].fields[1].name = "wrong";
  assert.equal((await evaluate(html, page))?.mismatches, 1);
  assert.equal(await evaluate("<input>".repeat(65), page), null);
  assert.equal(await evaluate('<input type="hidden">'.repeat(257), page), null);
  assert.equal(
    await evaluate("<input>", { ...page, source_url: "http://example.test" }),
    null,
  );
  process.stderr.write("DOM evaluator self-check passed\n");
}

const [out, ...files] = process.argv.slice(2);
if (out === "--self-test") await selfTest();
else {
  if (!out || !files.length)
    throw new Error(
      "Usage: jev-eval-dom <out.tsv> <raw/category/page.json>...",
    );
  const lines = [
    "page\tform\tno\tlocal\tjev\tconf\tfinal\tsource\ttype\tlabel\tcontext\tname\tplaceholder",
  ];
  let evaluated = 0,
    noSnapshot = 0,
    collectNull = 0,
    unmapped = 0,
    mismatchPages = 0;
  for (const file of files) {
    const path = resolve(file);
    const marker = `${sep}raw${sep}`;
    const at = path.lastIndexOf(marker);
    if (at < 0 || !path.endsWith(".json"))
      throw new Error(`Not a corpus JSON path: ${file}`);
    const key = path
      .slice(at + marker.length)
      .split(sep)
      .join("/");
    const snapshot =
      path.slice(0, at) +
      `${sep}html${sep}` +
      path.slice(at + marker.length, -5) +
      ".html";
    if (!existsSync(snapshot)) {
      noSnapshot++;
      process.stderr.write(`No snapshot: ${key}\n`);
      continue;
    }
    const page = JSON.parse(readFileSync(path, "utf8")) as Page;
    const result = await evaluate(readFileSync(snapshot, "utf8"), page);
    if (!result) {
      collectNull++;
      process.stderr.write(`Collect null: ${key}\n`);
      continue;
    }
    unmapped += result.mismatches;
    if (result.mismatches) {
      mismatchPages++;
      process.stderr.write(
        `Mapping mismatches: ${key}: ${result.mismatches}\n`,
      );
    }
    if (!result.lines.length) continue;
    evaluated++;
    lines.push(...result.lines.map((line) => `${key}\t${line}`));
  }
  writeFileSync(out, lines.join("\n") + "\n");
  process.stderr.write(
    `Pages evaluated: ${evaluated}; pages skipped: ${files.length - evaluated} ` +
      `(no snapshot: ${noSnapshot}, collect null: ${collectNull}, all unmapped: ${files.length - evaluated - noSnapshot - collectNull}); ` +
      `mapping mismatches: ${unmapped} fields on ${mismatchPages} pages; rows: ${lines.length - 1}\n`,
  );
}
