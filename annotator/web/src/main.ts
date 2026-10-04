// Annotation UI: pick a page, walk its fields with the keyboard, assign a kind to each.
import {
  loadPage,
  loadState,
  saveDone,
  saveLabel,
  type Kind,
  type PageDetail,
  type PageSummary,
  type Progress,
} from "./api.js";
import { byId, el, isTyping } from "./dom.js";
import {
  formHeading,
  matchKinds,
  or,
  renderKindButtons,
  renderPageHeader,
  renderRow,
  renderSidebar,
  rowsOf,
  type Row,
} from "./view.js";

interface App {
  kinds: readonly Kind[];
  kindByName: ReadonlyMap<string, Kind>;
  pages: PageSummary[];
  labelFile: string;
  page: PageDetail | null;
  rows: Row[];
  selected: number;
  filter: string;
  onlyOpen: boolean;
}

const app: App = {
  kinds: [],
  kindByName: new Map(),
  pages: [],
  labelFile: "",
  page: null,
  rows: [],
  selected: 0,
  filter: "",
  onlyOpen: false,
};

const ui = {
  sidebar: byId("sidebar", HTMLElement),
  main: byId("main", HTMLElement),
  kinds: byId("kinds", HTMLElement),
  filter: byId("filter", HTMLInputElement),
  unsure: byId("unsure", HTMLInputElement),
  note: byId("note", HTMLTextAreaElement),
  clear: byId("clear", HTMLButtonElement),
  onlyOpen: byId("only-open", HTMLInputElement),
  status: byId("status", HTMLElement),
  overall: byId("overall", HTMLElement),
  selection: byId("selection", HTMLElement),
};

// Saves run one after another so a fast sequence of keys cannot reorder writes.
let queue: Promise<void> = Promise.resolve();

function setStatus(text: string, error = false): void {
  ui.status.textContent = text;
  ui.status.classList.toggle("error", error);
}

function enqueue(task: () => Promise<void>): void {
  queue = queue.then(task).catch((error: unknown) => {
    setStatus(`保存できませんでした: ${error instanceof Error ? error.message : String(error)}`, true);
  });
}

function updateProgress(progress: Progress): void {
  app.pages = app.pages.map((p) => (p.key === progress.key ? { ...p, ...progress } : p));
  if (app.page?.key === progress.key) {
    app.page.progress = progress;
  }
  renderOverall();
  renderSidebarPane();
}

function renderOverall(): void {
  const fields = app.pages.reduce((sum, p) => sum + p.fields, 0);
  const labelled = app.pages.reduce((sum, p) => sum + p.labelled, 0);
  const done = app.pages.filter((p) => p.done).length;
  ui.overall.textContent =
    `${String(labelled)} / ${String(fields)} 欄・完了 ${String(done)} / ${String(app.pages.length)} ページ`;
  ui.overall.title = `保存先: ${app.labelFile}`;
}

function renderSidebarPane(): void {
  ui.sidebar.replaceChildren(
    renderSidebar(app.pages, app.page?.key ?? null, app.onlyOpen, (key) => {
      showPage(key);
    }),
  );
}

function renderMain(): void {
  const { page } = app;
  if (!page) {
    ui.main.replaceChildren(el("p", { className: "empty", text: "左の一覧からページを選んでください。" }));
    return;
  }
  const nodes: HTMLElement[] = [renderPageHeader(page, toggleDone)];
  let form = -1;
  app.rows.forEach((row, position) => {
    if (row.form !== form) {
      form = row.form;
      nodes.push(formHeading(row));
    }
    nodes.push(
      renderRow(row, app.kindByName, position === app.selected, () => {
        select(position);
      }),
    );
  });
  if (app.rows.length === 0) {
    nodes.push(el("p", { className: "empty", text: "入力できる欄がありません。" }));
  }
  ui.main.replaceChildren(...nodes);
}

function currentRow(): Row | undefined {
  return app.rows[app.selected];
}

function renderSelection(): void {
  const row = currentRow();
  ui.selection.textContent = row
    ? `選択中: フォーム${String(row.form)} #${String(row.field.index)} ${or(row.field.label, row.field.name)}`
    : "欄が選ばれていません";
}

function renderPicker(): void {
  const answer = currentRow()?.field.answer ?? null;
  ui.kinds.replaceChildren(
    renderKindButtons(matchKinds(app.kinds, app.filter), answer?.kind ?? null, (kind) => {
      assign(kind, true);
    }),
  );
  ui.unsure.checked = answer?.unsure ?? false;
  if (document.activeElement !== ui.note) {
    ui.note.value = answer?.note ?? "";
  }
  renderSelection();
}

function select(position: number): void {
  app.selected = Math.max(0, Math.min(app.rows.length - 1, position));
  renderMain();
  renderPicker();
  ui.main.querySelector(".row.selected")?.scrollIntoView({ block: "nearest" });
}

function save(kind: string | null, unsure: boolean, note: string): void {
  const { page } = app;
  const row = currentRow();
  if (!page || !row) {
    return;
  }
  const change = { page: page.key, form: row.form, index: row.field.index, kind, unsure, note };
  enqueue(async () => {
    setStatus("保存中…");
    const result = await saveLabel(change);
    row.field.answer = result.answer;
    updateProgress(result.progress);
    renderMain();
    renderPicker();
    setStatus("保存しました");
  });
}

function assign(kind: string, advance: boolean): void {
  const answer = currentRow()?.field.answer;
  save(kind, answer?.unsure ?? false, answer?.note ?? "");
  if (advance) {
    select(app.selected + 1);
  }
}

function updateCurrent(unsure: boolean, note: string): void {
  const answer = currentRow()?.field.answer;
  if (!answer) {
    setStatus("先に種類を選んでください", true);
    ui.unsure.checked = false;
    return;
  }
  save(answer.kind, unsure, note);
}

function toggleDone(): void {
  const { page } = app;
  if (!page) {
    return;
  }
  const done = !page.progress.done;
  enqueue(async () => {
    updateProgress(await saveDone(page.key, done));
    renderMain();
    setStatus(done ? "ページを完了にしました" : "完了を解除しました");
  });
}

async function openPage(key: string): Promise<void> {
  setStatus("読み込み中…");
  const page = await loadPage(key);
  app.page = page;
  app.rows = rowsOf(page);
  const firstOpen = app.rows.findIndex((row) => !row.field.answer);
  app.selected = Math.max(0, firstOpen);
  history.replaceState(null, "", `#page=${encodeURIComponent(key)}`);
  renderSidebarPane();
  ui.sidebar.querySelector(".page-item.current")?.scrollIntoView({ block: "center" });
  ui.main.scrollTop = 0;
  select(app.selected);
  setStatus("");
}

const describe = (error: unknown): string => (error instanceof Error ? error.message : String(error));

function showPage(key: string): void {
  openPage(key).catch((error: unknown) => {
    setStatus(`ページを開けませんでした: ${describe(error)}`, true);
  });
}

function stepPage(offset: number): void {
  const visible = app.pages.filter((p) => !app.onlyOpen || !p.done || p.key === app.page?.key);
  const position = visible.findIndex((p) => p.key === app.page?.key);
  const next = visible[position + offset];
  if (next) {
    showPage(next.key);
  }
}

function repeatPrevious(): void {
  const previous = app.rows[app.selected - 1]?.field.answer;
  if (previous) {
    assign(previous.kind, true);
  }
}

const keyActions: Readonly<Record<string, () => void>> = {
  j: () => {
    select(app.selected + 1);
  },
  ArrowDown: () => {
    select(app.selected + 1);
  },
  k: () => {
    select(app.selected - 1);
  },
  ArrowUp: () => {
    select(app.selected - 1);
  },
  "/": () => {
    ui.filter.focus();
  },
  o: () => {
    assign("OTHER", true);
  },
  ".": repeatPrevious,
  u: () => {
    updateCurrent(!(currentRow()?.field.answer?.unsure ?? false), ui.note.value);
  },
  n: () => {
    ui.note.focus();
  },
  x: () => {
    save(null, false, "");
  },
  d: toggleDone,
  "]": () => {
    stepPage(1);
  },
  "[": () => {
    stepPage(-1);
  },
};

function onKey(event: KeyboardEvent): void {
  if (event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) {
    return;
  }
  const action = keyActions[event.key];
  if (action) {
    event.preventDefault();
    action();
  }
}

function onFilterKey(event: KeyboardEvent): void {
  if (event.isComposing) {
    return;
  }
  if (event.key === "Enter") {
    const first = matchKinds(app.kinds, app.filter)[0];
    if (first) {
      assign(first.name, true);
    }
  }
  if (event.key === "Enter" || event.key === "Escape") {
    event.preventDefault();
    ui.filter.value = "";
    app.filter = "";
    ui.filter.blur();
    renderPicker();
  }
}

function bindEvents(): void {
  document.addEventListener("keydown", onKey);
  ui.filter.addEventListener("input", () => {
    app.filter = ui.filter.value;
    renderPicker();
  });
  ui.filter.addEventListener("keydown", onFilterKey);
  ui.unsure.addEventListener("change", () => {
    updateCurrent(ui.unsure.checked, ui.note.value);
  });
  ui.note.addEventListener("change", () => {
    updateCurrent(ui.unsure.checked, ui.note.value);
  });
  ui.note.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      ui.note.blur();
    }
  });
  ui.clear.addEventListener("click", () => {
    save(null, false, "");
  });
  window.addEventListener("hashchange", onHashChange);
  ui.onlyOpen.addEventListener("change", () => {
    app.onlyOpen = ui.onlyOpen.checked;
    renderSidebarPane();
  });
}

const requestedPage = (): string | null => new URLSearchParams(location.hash.slice(1)).get("page");

function onHashChange(): void {
  const key = requestedPage();
  if (key !== null && key !== app.page?.key && app.pages.some((p) => p.key === key)) {
    showPage(key);
  }
}

async function start(): Promise<void> {
  bindEvents();
  const state = await loadState();
  app.kinds = state.kinds;
  app.kindByName = new Map(state.kinds.map((kind) => [kind.name, kind]));
  app.pages = [...state.pages];
  app.labelFile = state.labelFile;
  renderOverall();
  renderSidebarPane();
  renderPicker();
  const requested = requestedPage();
  const initial = app.pages.find((p) => p.key === requested) ?? app.pages.find((p) => !p.done);
  if (initial) {
    await openPage(initial.key);
  } else {
    renderMain();
  }
}

start().catch((error: unknown) => {
  setStatus(`起動できませんでした: ${error instanceof Error ? error.message : String(error)}`, true);
});
