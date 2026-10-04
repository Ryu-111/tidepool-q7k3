// Typed access to the local annotation server. Responses are shape-checked at the top level
// before use, and every change is sent as JSON so the server's origin checks apply.

export interface Kind {
  readonly name: string;
  readonly group: string;
  readonly label: string;
}

export interface Progress {
  readonly key: string;
  readonly fields: number;
  readonly labelled: number;
  readonly done: boolean;
}

export interface PageSummary extends Progress {
  readonly category: string;
  readonly host: string;
}

export interface State {
  readonly kinds: readonly Kind[];
  readonly pages: readonly PageSummary[];
  readonly labelFile: string;
}

export interface Answer {
  readonly kind: string;
  readonly unsure: boolean;
  readonly note: string;
  readonly stale: boolean;
}

export interface Field {
  readonly index: number;
  readonly tag: string;
  readonly type: string;
  readonly name: string;
  readonly htmlId: string;
  readonly label: string;
  readonly near: readonly string[];
  readonly legend: string;
  readonly placeholder: string;
  readonly autocomplete: string;
  readonly ariaLabel: string;
  readonly title: string;
  readonly maxlength: string;
  readonly inputmode: string;
  readonly pattern: string;
  readonly required: boolean;
  readonly options: readonly string[];
  readonly recorded: Recorded | null;
  answer: Answer | null;
}

export interface Recorded {
  readonly kind: string;
  readonly source: "local" | "jev" | "none";
  readonly confidence: number | null;
  readonly outcome: "kept" | "edited" | "cleared" | "typed";
}

export interface Form {
  readonly number: number;
  readonly outsideForm: boolean;
  readonly fields: readonly Field[];
}

export interface PageDetail {
  readonly key: string;
  readonly category: string;
  readonly host: string;
  readonly url: string;
  readonly fetchedAt: string;
  readonly forms: readonly Form[];
  progress: Progress;
}

export interface LabelChange {
  readonly page: string;
  readonly form: number;
  readonly index: number;
  readonly kind: string | null;
  readonly unsure: boolean;
  readonly note: string;
}

export class ApiError extends Error {
  public constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

async function request(path: string, init?: RequestInit): Promise<Record<string, unknown>> {
  const response = await fetch(path, { credentials: "same-origin", ...init });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const message = isRecord(body) && typeof body["error"] === "string" ? body["error"] : "";
    throw new ApiError(message !== "" ? message : response.statusText, response.status);
  }
  if (!isRecord(body)) {
    throw new ApiError("unexpected response", response.status);
  }
  return body;
}

function expectArrays(body: Record<string, unknown>, ...keys: string[]): void {
  for (const key of keys) {
    if (!Array.isArray(body[key])) {
      throw new ApiError(`response lacks ${key}`, 200);
    }
  }
}

async function put(path: string, body: object): Promise<Record<string, unknown>> {
  return request(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function loadState(): Promise<State> {
  const body = await request("/api/state");
  expectArrays(body, "kinds", "pages");
  return body as unknown as State;
}

export async function loadPage(key: string): Promise<PageDetail> {
  const body = await request(`/api/page?key=${encodeURIComponent(key)}`);
  expectArrays(body, "forms");
  return body as unknown as PageDetail;
}

export async function saveLabel(
  change: LabelChange,
): Promise<{ answer: Answer | null; progress: Progress }> {
  const body = await put("/api/label", change);
  if (!isRecord(body["progress"])) {
    throw new ApiError("response lacks progress", 200);
  }
  return body as unknown as { answer: Answer | null; progress: Progress };
}

export async function saveDone(page: string, done: boolean): Promise<Progress> {
  const body = await put("/api/done", { page, done });
  const progress = body["progress"];
  if (!isRecord(progress)) {
    throw new ApiError("response lacks progress", 200);
  }
  return progress as unknown as Progress;
}
