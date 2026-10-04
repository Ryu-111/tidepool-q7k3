// Rendering of the three panes. Functions here build nodes from data and report clicks through
// callbacks; they hold no state.
import type { Answer, Field, Kind, PageDetail, PageSummary, Recorded } from "./api.js";
import { el } from "./dom.js";

export interface Row {
  readonly form: number;
  readonly outsideForm: boolean;
  readonly field: Field;
}

const OPTIONS_SHOWN = 6;

/** [text], or [fallback] when it is empty. */
export const or = (text: string, fallback: string): string => (text !== "" ? text : fallback);

export const rowsOf = (page: PageDetail): Row[] =>
  page.forms.flatMap((form) =>
    form.fields.map((field) => ({ form: form.number, outsideForm: form.outsideForm, field })),
  );

const percent = (part: number, whole: number): string =>
  whole === 0 ? "100%" : `${String(Math.round((part / whole) * 100))}%`;

function progressBar(labelled: number, fields: number): HTMLElement {
  const bar = el("span", { className: "bar" }, el("span", { className: "bar-fill" }));
  bar.style.setProperty("--fill", percent(labelled, fields));
  return bar;
}

export function renderSidebar(
  pages: readonly PageSummary[],
  current: string | null,
  onlyOpen: boolean,
  onSelect: (key: string) => void,
): HTMLElement {
  const list = el("ul", { className: "page-list" });
  let category = "";
  for (const page of pages) {
    if (onlyOpen && page.done && page.key !== current) {
      continue;
    }
    if (page.category !== category) {
      category = page.category;
      list.append(el("li", { className: "category", text: category }));
    }
    const state = page.done ? "done" : page.labelled > 0 ? "started" : "new";
    const item = el(
      "button",
      {
        className: `page-item ${state}${page.key === current ? " current" : ""}`,
        title: page.key,
        attrs: { type: "button" },
        onClick: () => {
          onSelect(page.key);
        },
      },
      el("span", { className: "page-host", text: or(page.host, page.key) }),
      el("span", { className: "page-count", text: `${String(page.labelled)}/${String(page.fields)}` }),
      progressBar(page.labelled, page.fields),
    );
    list.append(el("li", {}, item));
  }
  return list;
}

function chip(name: string, value: string): HTMLElement | null {
  return value !== "" ? el("span", { className: "chip" }, el("b", { text: name }), value) : null;
}

function optionsList(options: readonly string[]): HTMLElement | null {
  if (options.length === 0) {
    return null;
  }
  const head = options.slice(0, OPTIONS_SHOWN).join(" / ");
  if (options.length <= OPTIONS_SHOWN) {
    return el("div", { className: "options", text: `選択肢: ${head}` });
  }
  return el(
    "details",
    { className: "options" },
    el("summary", { text: `選択肢: ${head} …ほか${String(options.length - OPTIONS_SHOWN)}件` }),
    el("div", { text: options.join(" / ") }),
  );
}

function evidence(field: Field): HTMLElement {
  return el(
    "div",
    { className: "evidence" },
    el(
      "div",
      { className: "caption" },
      field.label !== ""
        ? el("span", { className: "label", text: field.label })
        : el("span", { className: "label none", text: "（label要素なし）" }),
      field.legend !== "" ? el("span", { className: "legend", text: `［${field.legend}］` }) : null,
    ),
    field.near.length > 0
      ? el("div", { className: "near", text: field.near.join("  ›  ") })
      : null,
    field.placeholder !== "" ? el("div", { className: "placeholder", text: `例: ${field.placeholder}` }) : null,
    el(
      "div",
      { className: "chips" },
      chip("name", field.name),
      chip("id", field.htmlId),
      chip("autocomplete", field.autocomplete),
      chip("maxlength", field.maxlength),
      chip("inputmode", field.inputmode),
      chip("pattern", field.pattern),
      chip("aria-label", field.ariaLabel),
      chip("title", field.title),
    ),
    optionsList(field.options),
  );
}

function answerBadge(answer: Answer | null, kinds: ReadonlyMap<string, Kind>): HTMLElement {
  if (!answer) {
    return el("div", { className: "answer empty", text: "未入力" });
  }
  const kind = kinds.get(answer.kind);
  return el(
    "div",
    { className: `answer${answer.kind === "OTHER" ? " other" : ""}` },
    el("span", { className: "answer-name", text: answer.kind }),
    el("span", { className: "answer-label", text: kind?.label ?? "" }),
    answer.unsure ? el("span", { className: "flag unsure", text: "自信なし" }) : null,
    answer.stale ? el("span", { className: "flag stale", text: "欄が変更された" }) : null,
    answer.note !== "" ? el("span", { className: "note", text: `メモ: ${answer.note}` }) : null,
  );
}

function recordedLine(recorded: Recorded | null): HTMLElement | null {
  if (recorded === null) {
    return null;
  }
  const sources = { local: "ローカル", jev: "Jev", none: "判定なし" };
  const outcomes = { kept: "変更なし", edited: "書き直し", cleared: "消去", typed: "自分で入力" };
  const confidence = recorded.confidence === null ? "" : ` ${recorded.confidence.toFixed(2)}`;
  return el("div", {
    className: "recorded",
    text: `記録: ${recorded.kind}（${sources[recorded.source]}${confidence}）→ ${outcomes[recorded.outcome]}`,
  });
}

export function renderRow(
  row: Row,
  kinds: ReadonlyMap<string, Kind>,
  selected: boolean,
  onSelect: () => void,
): HTMLElement {
  const { field } = row;
  return el(
    "div",
    {
      className: `row${selected ? " selected" : ""}${field.answer ? " answered" : ""}`,
      onClick: onSelect,
    },
    el(
      "div",
      { className: "meta" },
      el("span", { className: "index", text: `#${String(field.index)}` }),
      el("span", { className: `type type-${field.type}`, text: field.type }),
      field.required ? el("span", { className: "required", text: "必須" }) : null,
    ),
    el("div", {}, evidence(field), recordedLine(field.recorded)),
    answerBadge(field.answer, kinds),
  );
}

export function renderPageHeader(page: PageDetail, onToggleDone: () => void): HTMLElement {
  const { progress } = page;
  const link = el("a", {
    className: "source",
    text: page.url,
    attrs: { href: page.url, target: "_blank", rel: "noopener noreferrer" },
  });
  return el(
    "header",
    { className: "page-header" },
    el("h2", { text: or(page.host, page.key) }),
    el("div", { className: "page-meta" }, `${page.category} · ${page.key} · 取得 ${page.fetchedAt}`),
    link,
    el(
      "div",
      { className: "page-actions" },
      el("span", {
        text: `${String(progress.labelled)} / ${String(progress.fields)} 欄 (${percent(progress.labelled, progress.fields)})`,
      }),
      el("button", {
        className: progress.done ? "done-toggle on" : "done-toggle",
        text: progress.done ? "完了済み（d で解除）" : "このページを完了にする（d）",
        attrs: { type: "button" },
        onClick: onToggleDone,
      }),
    ),
  );
}

export function formHeading(row: Row): HTMLElement {
  return el("h3", {
    className: "form-heading",
    text: row.outsideForm ? `フォーム外の欄 (#${String(row.form)})` : `フォーム ${String(row.form)}`,
  });
}

const normalize = (text: string): string => text.normalize("NFKC").toLowerCase().trim();

export function matchKinds(kinds: readonly Kind[], query: string): Kind[] {
  const q = normalize(query);
  if (q === "") {
    return [...kinds];
  }
  const hits = kinds.filter((kind) =>
    [kind.name, kind.label, kind.group].some((text) => normalize(text).includes(q)),
  );
  const starts = (kind: Kind): number => (normalize(kind.name).startsWith(q) ? 0 : 1);
  return hits.sort((a, b) => starts(a) - starts(b));
}

export function renderKindButtons(
  kinds: readonly Kind[],
  current: string | null,
  onPick: (kind: string) => void,
): HTMLElement {
  const box = el("div", { className: "kinds" });
  let group = "";
  kinds.forEach((kind, position) => {
    if (kind.group !== group) {
      group = kind.group;
      box.append(el("div", { className: "kind-group", text: group }));
    }
    const first = position === 0 ? " first" : "";
    box.append(
      el(
        "button",
        {
          className: `kind${kind.name === current ? " current" : ""}${first}`,
          attrs: { type: "button" },
          onClick: () => {
            onPick(kind.name);
          },
        },
        el("span", { className: "kind-name", text: kind.name }),
        el("span", { className: "kind-label", text: kind.label }),
      ),
    );
  });
  return box;
}
