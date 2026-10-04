// Keep raw control positions, including radio/checkbox controls omitted by the annotation API.
import type { Field } from "./api.js";
import type { Row } from "./view.js";

const SKIPPED = new Set(["hidden", "submit", "button", "reset", "image", "file"]);

function controlType(node: Element): string {
  return node.localName === "input"
    ? (node.getAttribute("type") ?? "text").toLowerCase()
    : node.localName;
}

function controlGroups(doc: Document): { forms: HTMLElement[][]; outside: HTMLElement[] } {
  const byForm = new Map<Element, HTMLElement[]>();
  const outside: HTMLElement[] = [];
  for (const node of doc.querySelectorAll<HTMLElement>("input, select, textarea")) {
    if (node.localName === "input" && SKIPPED.has(controlType(node))) {
      continue;
    }
    const form = node.closest("form");
    if (form === null) {
      outside.push(node);
    } else {
      const controls = byForm.get(form) ?? [];
      controls.push(node);
      byForm.set(form, controls);
    }
  }
  const forms = [...doc.querySelectorAll("form")].flatMap((form) => {
    const controls = byForm.get(form);
    return controls ? [controls] : [];
  });
  return { forms, outside };
}

// Extraction collapsed whitespace and clipped long attribute values; compare the same way.
const sameText = (actual: string | null, recorded: string): boolean =>
  recorded === "" || (actual ?? "").replace(/\s+/g, " ").trim().startsWith(recorded);

function matches(node: Element, field: Field): boolean {
  return node.localName === field.tag && controlType(node) === field.type &&
    sameText(node.getAttribute("name"), field.name) && sameText(node.id, field.htmlId);
}

export function mapControls(doc: Document, rows: readonly Row[]): Map<number, HTMLElement> {
  const { forms, outside } = controlGroups(doc);
  const mapped = new Map<number, HTMLElement>();
  rows.forEach((row, position) => {
    const controls = row.outsideForm ? outside : forms[row.form];
    const node = controls?.[row.field.index];
    if (node && matches(node, row.field)) {
      mapped.set(position, node);
    }
  });
  return mapped;
}
