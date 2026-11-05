import { DiagnosticPayload } from "/static/diagnostic-payload.js";
class ReportController {
  constructor({ getUser }) {
    this.#getUser = getUser;
    this.#requests = [];
    this.#actions = [];
    this.#queue = [];
    this.#seen = new Set();
    this.#contextProvider = () => ({});
    this.#sending = false;
    this.#automaticCount = 0;
    this.#restoredUser = undefined;
    this.#reference = () => crypto.randomUUID().replaceAll("-", "");
    this.#node = (tag, text, cls) => {
      const e = document.createElement(tag);
      if (text !== undefined) e.textContent = text;
      if (cls) e.className = cls;
      return e;
    };
    this.#bindDocumentClick();
    this.#bindDocumentChange();
    addEventListener("error", (event) =>
      this.#action("browser_error", {
        message: event.message,
        filename: event.filename,
        line: event.lineno,
      }),
    );
    addEventListener("unhandledrejection", (event) =>
      this.#action("unhandled_rejection", {
        message: String(event.reason?.message || event.reason).slice(0, 1000),
      }),
    );
    this.#createFeedbackFields();
    this.#createFeedbackActions();
    this.#restore();
    this.#interval = setInterval(this.#drain.bind(this), 10000);
    addEventListener("online", this.#drain.bind(this));
    addEventListener("pagehide", () => {
      this.#persist();
      clearInterval(this.#interval);
    });
  }
  #getUser;
  #requests;
  #actions;
  #queue;
  #seen;
  #contextProvider;
  #sending;
  #automaticCount;
  #restoredUser;
  #reference;
  #node;
  #dialog;
  #form;
  #header;
  #heading;
  #content;
  #categoryLabel;
  #category;
  #commentLabel;
  #comment;
  #note;
  #error;
  #footer;
  #cancel;
  #submit;
  #interval;
  #clean(value, depth = 0) {
    if (depth > 22)
      return {
        _truncated: true,
        reason: "nesting limit",
      };
    if (Array.isArray(value))
      return value.slice(0, 300).map((v) => this.#clean(v, depth + 1));
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.entries(value)
          .slice(0, 500)
          .map(([k, v]) => [
            k,
            /password|cookie|authorization|secret|api.?key|access.?token|refresh.?token|id.?token|private.?key|access.?key|secter|verifier|nonce/i.test(
              k,
            ) ||
            (k === "input" &&
              value.loc?.some((p) =>
                /password|cookie|authorization|secret|token|key/i.test(
                  String(p),
                ),
              ))
              ? "[REDACTED]"
              : this.#clean(v, depth + 1),
          ]),
      );
    if (typeof value === "string")
      return value
        .replace(
          /sk-(?:proj-)?[A-Za-z0-9_-]{12,}|GOCSPX-[A-Za-z0-9_-]{10,}|Bearer\s+[A-Za-z0-9._~+/-]{12,}/g,
          "[REDACTED]",
        )
        .slice(0, 250000);
    return value;
  }
  #bounded(value, max = 1200000) {
    const result = this.#clean(value),
      text = JSON.stringify(result),
      bytes = new TextEncoder().encode(text);
    return bytes.length <= max
      ? result
      : {
          _truncated: true,
          reason: "browser context byte limit",
          serialized_prefix: new TextDecoder().decode(
            bytes.slice(0, max - 200),
          ),
        };
  }
  #action(type, value) {
    this.#actions.push({
      at: new Date().toISOString(),
      type,
      ...this.#clean(value),
    });
    if (this.#actions.length > 100) this.#actions.shift();
  }
  #persist() {
    const user = (0, this.#getUser)();
    if (user)
      try {
        sessionStorage.setItem(
          `mathpdf-reports-${user.id}`,
          JSON.stringify(this.#queue.slice(-10)),
        );
      } catch {}
  }
  #restore() {
    const user = (0, this.#getUser)();
    if (!user || this.#restoredUser === user.id) return;
    this.#restoredUser = user.id;
    try {
      for (const item of JSON.parse(
        sessionStorage.getItem(`mathpdf-reports-${user.id}`) || "[]",
      ))
        if (
          item &&
          item.context &&
          !this.#queue.some(
            (q) => q.origin === item.origin && q.request_id === item.request_id,
          )
        ) {
          this.#queue.push(item);
          if (item.request_id) this.#seen.add(item.request_id);
        }
    } catch {}
  }
  async #snapshot() {
    let active;
    try {
      active = await (0, this.#contextProvider)();
    } catch (error) {
      active = {
        _unavailable: true,
        reason: error.name,
      };
    }
    return this.#bounded({
      page: {
        path: location.pathname + location.search,
        title: document.title,
        build: document.querySelector("meta[name=mathpdf-build]")?.content,
        width: innerWidth,
        height: innerHeight,
        scroll: {
          x: scrollX,
          y: scrollY,
        },
        language: navigator.language,
        time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        user_agent: navigator.userAgent,
      },
      active,
      selection: getSelection()?.toString().slice(0, 5000),
      recent_actions: this.#actions.slice(-100),
      recent_requests: this.#requests.slice(-30),
    });
  }
  async #send(report) {
    const user = (0, this.#getUser)();
    if (!user) throw new Error("Sign in before sending feedback.");
    const controller = new AbortController(),
      timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("/api/reports", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          "X-MathPDF-User": user.id,
          "X-MathPDF-Request-ID": (0, this.#reference)(),
        },
        body: JSON.stringify(report),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok)
        throw new Error(
          result?.detail || `Report service returned HTTP ${response.status}.`,
        );
      return result;
    } finally {
      clearTimeout(timer);
    }
  }
  async #drain() {
    this.#restore();
    if (this.#sending || !this.#queue.length || !(0, this.#getUser)()) return;
    this.#sending = true;
    try {
      while (this.#queue.length) {
        await this.#send(this.#queue[0]);
        this.#queue.shift();
        this.#persist();
      }
    } catch {
    } finally {
      this.#sending = false;
    }
  }
  async #automatic(request_id, extra) {
    if (
      !(0, this.#getUser)() ||
      this.#seen.has(request_id) ||
      this.#automaticCount >= 10
    )
      return;
    this.#seen.add(request_id);
    this.#automaticCount++;
    this.#queue.push({
      origin: "automatic",
      category: "bug",
      request_id,
      context: this.#bounded({
        ...(await this.#snapshot()),
        failure: extra,
      }),
    });
    this.#persist();
    this.#drain();
  }
  async #observe(path, options, response) {
    const url = new URL(path, location.origin);
    if (
      url.origin !== location.origin ||
      !url.pathname.startsWith("/api/") ||
      url.pathname.startsWith("/api/reports") ||
      url.pathname === "/api/client-errors"
    )
      return;
    const body = DiagnosticPayload.request(options),
      data = await DiagnosticPayload.response(response);
    const requestId =
      data?.request_id ||
      response.headers.get("x-mathpdf-request-id") ||
      (0, this.#reference)();
    const entry = this.#bounded(
      {
        at: new Date().toISOString(),
        path: url.pathname + url.search,
        method: options.method || "GET",
        status: response.status,
        request_id: response.headers.get("x-mathpdf-request-id"),
        request: body,
        response: data,
      },
      180000,
    );
    // Polling snapshots repeat large generated content; retain only terminal failures and mutations.
    if (
      (options.method || "GET") !== "GET" ||
      response.status >= 400 ||
      data?.status === "failed"
    ) {
      this.#requests.push(entry);
      if (this.#requests.length > 30) this.#requests.shift();
    }
    const expectedQuota =
      (response.status === 429 && data?.code === "generation_limit") ||
      (data?.status === "failed" && data?.limit?.code === "generation_limit");
    if (!expectedQuota && (response.status >= 400 || data?.status === "failed"))
      await this.#automatic(requestId, entry);
  }
  #bindDocumentClick() {
    document.addEventListener(
      "click",
      (event) => {
        if (event.target.closest("#feedback-dialog")) return;
        const e = event.target.closest("button,a,summary");
        if (e)
          this.#action("click", {
            id: e.id,
            label:
              e.getAttribute("aria-label") ||
              e.textContent.trim().slice(0, 180),
          });
      },
      true,
    );
  }
  #bindDocumentChange() {
    document.addEventListener(
      "change",
      (event) => {
        const e = event.target;
        if (e.closest("#feedback-dialog") || e.type === "password") return;
        if (
          e.matches(
            "select,input[type=radio],input[type=checkbox],input[type=number]",
          ) ||
          ["context-comment", "set-name", "page", "zoom"].includes(e.id)
        )
          this.#action("change", {
            id: e.id,
            name: e.name,
            value: e.type === "checkbox" ? e.checked : e.value,
          });
      },
      true,
    );
  }
  #bindCancelClick() {
    this.#cancel.addEventListener("click", () => {
      if (!this.#submit.disabled) this.#dialog.close();
    });
  }
  #bindDialogCancel() {
    this.#dialog.addEventListener("cancel", (event) => {
      if (this.#submit.disabled) event.preventDefault();
    });
  }
  #bindFormSubmit() {
    this.#form.addEventListener("submit", async (event) => {
      event.preventDefault();
      this.#submit.disabled = this.#cancel.disabled = true;
      this.#error.hidden = true;
      try {
        const result = await this.#send({
          origin: "manual",
          category: this.#category.value,
          comment: this.#comment.value,
          request_id: this.#requests.at(-1)?.request_id || null,
          context: await this.#snapshot(),
        });
        this.#dialog.close();
        this.#comment.value = "";
        let toast = document.getElementById("report-receipt");
        if (!toast) {
          toast = (0, this.#node)("div", undefined, "status-message");
          toast.id = "report-receipt";
          toast.setAttribute("role", "status");
          document.body.append(toast);
        }
        toast.textContent = `Report sent. Reference: ${result.id}`;
        toast.hidden = false;
        setTimeout(() => (toast.hidden = true), 12000);
      } catch (failure) {
        this.#error.textContent = failure.message;
        this.#error.hidden = false;
      } finally {
        this.#submit.disabled = this.#cancel.disabled = false;
      }
    });
  }
  get api() {
    return {
      observe: this.#observe.bind(this),
      setContextProvider: (...args) => this.#api_setContextProvider(...args),
      button: (...args) => this.#api_button(...args),
    };
  }
  #api_setContextProvider(provider) {
    return (this.#contextProvider = provider);
  }
  #api_button() {
    const b = (0, this.#node)("button", "Report a problem", "secondary");
    b.type = "button";
    b.addEventListener("click", () => {
      this.#error.hidden = true;
      this.#dialog.showModal();
    });
    return b;
  }
  #createFeedbackActions() {
    this.#footer = (0, this.#node)("div", undefined, "dialog-footer");
    this.#cancel = (0, this.#node)("button", "Cancel", "secondary");
    this.#submit = (0, this.#node)("button", "Send report");
    this.#cancel.type = "button";
    this.#submit.type = "submit";
    this.#cancel.autofocus = true;
    this.#bindCancelClick();
    this.#bindDialogCancel();
    this.#footer.append(this.#cancel, this.#submit);
    this.#form.append(this.#header, this.#content, this.#footer);
    this.#dialog.append(this.#form);
    document.body.append(this.#dialog);
    this.#bindFormSubmit();
  }
  #createFeedbackFields() {
    this.#dialog = (0, this.#node)("dialog");
    this.#dialog.id = "feedback-dialog";
    this.#dialog.setAttribute("aria-labelledby", "feedback-heading");
    this.#form = (0, this.#node)("form");
    this.#header = (0, this.#node)("div", undefined, "dialog-header");
    this.#heading = (0, this.#node)("h2", "Report a problem");
    this.#heading.id = "feedback-heading";
    this.#header.append(this.#heading);
    this.#content = (0, this.#node)("div", undefined, "dialog-body");
    this.#categoryLabel = (0, this.#node)("label", "Issue type");
    this.#category = (0, this.#node)("select");
    this.#category.id = "feedback-category";
    this.#categoryLabel.htmlFor = this.#category.id;
    for (const [value, label] of [
      ["bug", "Something is broken"],
      ["incorrect_content", "Incorrect content"],
      ["formatting", "Formula or layout formatting"],
      ["too_slow", "Response takes too long"],
      ["answer_too_long", "Answer is too long"],
      ["other", "Other feedback"],
    ])
      this.#category.append(new Option(label, value));
    this.#commentLabel = (0, this.#node)("label", "What happened?");
    this.#comment = (0, this.#node)("textarea");
    this.#comment.id = "feedback-comment";
    this.#comment.rows = 4;
    this.#comment.maxLength = 5000;
    this.#comment.placeholder = "Describe what you expected and what you saw.";
    this.#commentLabel.htmlFor = this.#comment.id;
    this.#note = (0, this.#node)(
      "p",
      "Includes the current file/card, recent requests and actions, and relevant source files. Administrators can review this context. Passwords and credentials are excluded.",
      "field-note",
    );
    this.#error = (0, this.#node)("p", undefined, "error");
    this.#error.hidden = true;
    this.#error.setAttribute("role", "alert");
    this.#content.append(
      this.#categoryLabel,
      this.#category,
      this.#commentLabel,
      this.#comment,
      this.#note,
      this.#error,
    );
  }
}
/* Private diagnostic context and manual tester feedback; ingestion never reports itself. */
export function initialize({ getUser }) {
  return new ReportController({
    getUser,
  }).api;
}
