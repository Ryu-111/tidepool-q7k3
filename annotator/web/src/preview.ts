// The iframe survives list re-renders; only its annotations change after selection/save.
import type { PageDetail } from "./api.js";
import { byId, el } from "./dom.js";
import { mapControls } from "./preview-map.js";
import type { Row } from "./view.js";

const STORAGE_KEY = "jev-annotator-preview-styles";
const MARK = "data-jev-annotator-preview";
const HIGHLIGHTS = `
  [${MARK}="labelled"] { outline: 2px solid #2e8b5780 !important; outline-offset: 2px !important; }
  [${MARK}="selected"] { outline: 3px solid #2f6fdb !important; outline-offset: 3px !important; }
`;

function storedStyles(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) !== "0";
  } catch {
    return true;
  }
}

function rememberStyles(enabled: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
  } catch {
    // Preview still works when browser storage is unavailable.
  }
}

export class Preview {
  private readonly host = byId("preview", HTMLElement);
  private readonly workspace = byId("workspace", HTMLElement);
  private readonly parent = byId("main", HTMLElement);
  private readonly notice = el("p", { className: "preview-notice", attrs: { role: "status" } });
  private readonly styles = el("input", { attrs: { type: "checkbox" } });
  private frame: HTMLIFrameElement | null = null;
  private mapped = new Map<number, HTMLElement>();
  private rows: readonly Row[] = [];
  private selected = 0;

  public constructor(private readonly onSelect: (position: number) => void) {
    this.styles.checked = storedStyles();
  }

  public show(page: PageDetail, rows: readonly Row[], selected: number): void {
    this.rows = rows;
    this.selected = selected;
    this.mapped.clear();
    this.frame = null;
    this.workspace.classList.toggle("with-preview", page.snapshot);
    this.host.hidden = false;
    if (!page.snapshot) {
      this.notice.textContent = "スナップショットがありません。uv run jev-annotator fetch-pages で作成できます。";
      this.host.replaceChildren(this.notice);
      return;
    }
    const frame = el("iframe", {
      className: "preview-frame",
      attrs: { sandbox: "allow-same-origin", title: "収集したフォームのプレビュー" },
    });
    this.frame = frame;
    this.styles.onchange = () => {
      rememberStyles(this.styles.checked);
      this.load(frame, page.key);
    };
    frame.addEventListener("load", () => {
      this.connect(frame);
    });
    this.host.replaceChildren(
      el("div", { className: "preview-toolbar" },
        el("strong", { text: "フォームのプレビュー" }),
        el("label", {}, this.styles, " サイトのスタイルを読み込む")),
      this.notice, frame,
    );
    this.load(frame, page.key);
  }

  public update(selected: number, scroll = false): void {
    this.selected = selected;
    for (const [position, node] of this.mapped) {
      node.removeAttribute(MARK);
      if (position === selected) {
        node.setAttribute(MARK, "selected");
      } else if (this.rows[position]?.field.answer) {
        node.setAttribute(MARK, "labelled");
      }
    }
    if (scroll) {
      this.mapped.get(selected)?.scrollIntoView({ block: "center", inline: "nearest" });
    }
  }

  private load(frame: HTMLIFrameElement, key: string): void {
    this.mapped.clear();
    this.notice.textContent = "プレビューを読み込み中…";
    frame.src = `/snapshot?key=${encodeURIComponent(key)}&styles=${this.styles.checked ? "1" : "0"}`;
  }

  private connect(frame: HTMLIFrameElement): void {
    if (frame !== this.frame) {
      return;
    }
    try {
      const doc = frame.contentDocument;
      if (doc === null || doc.URL === "about:blank") {
        return;
      }
      // Nodes are adopted by the iframe document; corpus content never enters an HTML sink.
      doc.head.append(el("style", { text: HIGHLIGHTS }));
      this.mapped = mapControls(doc, this.rows);
      const mismatches = this.rows.length - this.mapped.size;
      this.notice.textContent = mismatches > 0
        ? `フォームの構造が収集時と異なる欄: ${String(mismatches)}`
        : "欄をクリックすると一覧で選択できます。青: 選択中 / 緑: ラベル済み";
      doc.addEventListener("click", (event) => {
        this.onClick(event);
      }, true);
      doc.addEventListener("submit", (event) => {
        event.preventDefault();
      }, true);
      this.update(this.selected, true);
    } catch {
      this.notice.textContent = "プレビューを読み込めませんでした。";
    }
  }

  private onClick(event: MouseEvent): void {
    event.preventDefault();
    // Avoid instanceof: controls belong to the iframe's separate JavaScript realm.
    const target = event.target;
    for (const [position, node] of this.mapped) {
      if (target === node || (target !== null && node.contains(target as Node))) {
        this.onSelect(position);
        break;
      }
    }
    window.focus();
    this.parent.focus({ preventScroll: true });
  }
}

export function bindSidebarToggle(): void {
  const button = byId("sidebar-toggle", HTMLButtonElement);
  button.addEventListener("click", () => {
    const collapsed = document.body.classList.toggle("sidebar-collapsed");
    byId("sidebar", HTMLElement).hidden = collapsed;
    button.setAttribute("aria-expanded", String(!collapsed));
    button.textContent = collapsed ? "ページ一覧を表示" : "ページ一覧を隠す";
  });
}
