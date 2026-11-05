/* One cancellable JSON request, with diagnostics independent of account UI. */
export class JsonApiCall {
  #request;
  #report;
  #referenceFactory;
  #routeLabel;
  #signIn;
  #path;
  #settings;
  #controller;
  #signal;
  #cancelled;
  #timer;
  #reference;
  #response;
  #reported = false;
  #receivedBytes = null;
  constructor({ request, report, reference, routeLabel, signIn }) {
    this.#request = request;
    this.#report = report;
    this.#referenceFactory = reference;
    this.#routeLabel = routeLabel;
    this.#signIn = signIn;
  }
  async execute(path, options = {}) {
    this.#path = path;
    this.#prepareCancellation(options);
    this.#reference = this.#referenceFactory();
    try {
      return await this.#receive();
    } catch (error) {
      throw this.#classifyFailure(error);
    } finally {
      clearTimeout(this.#timer);
      this.#signal?.removeEventListener("abort", this.#cancelled);
    }
  }
  #prepareCancellation(options) {
    const {
      timeoutMs = options.body instanceof FormData ? 180000 : 30000,
      signal,
      ...settings
    } = options;
    this.#settings = settings;
    this.#signal = signal;
    this.#controller = new AbortController();
    this.#cancelled = () => this.#controller.abort(signal.reason);
    if (signal?.aborted) this.#cancelled();
    else
      signal?.addEventListener("abort", this.#cancelled, {
        once: true,
      });
    this.#timer = setTimeout(
      () =>
        this.#controller.abort(
          new Error("The server did not respond in time. Please try again."),
        ),
      timeoutMs,
    );
  }
  async #receive() {
    const headers =
      this.#settings.body instanceof FormData
        ? {}
        : {
            "Content-Type": "application/json",
          };
    this.#response = await this.#request(this.#path, {
      ...this.#settings,
      signal: this.#controller.signal,
      headers: {
        ...headers,
        ...this.#settings.headers,
        "X-MathPDF-Request-ID": this.#reference,
      },
    });
    if (this.#response.status === 204) return null;
    const mime = (this.#response.headers.get("Content-Type") || "")
      .split(";")[0]
      .trim()
      .toLowerCase();
    this.#requireJson(mime);
    const data = await this.#decode(mime);
    this.#requireSuccess(data);
    return data;
  }
  #requireJson(mime) {
    if (mime === "application/json" || mime.endsWith("+json")) return;
    const error = this.#failure(
      `Expected JSON but received ${mime || "an unknown content type"} (HTTP ${this.#response.status}). Reload this page.`,
      "unexpected_content_type",
    );
    if (
      this.#response.redirected &&
      this.#routeLabel(this.#response.url) === "/login"
    )
      this.#signIn();
    throw error;
  }
  async #decode(mime) {
    try {
      const text = await this.#response.text();
      this.#receivedBytes = new TextEncoder().encode(text).length;
      return JSON.parse(text);
    } catch {
      if (this.#controller.signal.aborted) throw this.#controller.signal.reason;
      throw this.#failure(
        `The API response contains invalid or empty JSON (HTTP ${this.#response.status}, ${mime}).`,
        "invalid_json",
      );
    }
  }
  #requireSuccess(data) {
    if (this.#response.ok) return;
    if (this.#response.status === 429 && data?.code === "generation_limit") {
      throw Object.assign(new Error(data.detail), data, {
        status: 429,
      });
    }
    throw this.#failure(
      `${typeof data?.detail === "string" ? data.detail : "The request could not be completed"} (HTTP ${this.#response.status}).`,
      "http_error",
    );
  }
  #failure(message, event) {
    this.#reported = true;
    const id = this.#report(
      event,
      this.#path,
      this.#settings.method,
      this.#reference,
      this.#response,
      this.#receivedBytes,
    );
    return Object.assign(new Error(`${message} Reference: ${id}`), {
      status: this.#response?.status,
    });
  }
  #classifyFailure(error) {
    if (this.#controller.signal.aborted) {
      if (this.#controller.signal.reason?.name === "AbortError")
        return this.#controller.signal.reason;
      return this.#reported
        ? error
        : this.#failure(
            this.#controller.signal.reason?.message || "The request timed out.",
            "timeout",
          );
    }
    if (error instanceof TypeError && !this.#reported) {
      return this.#failure(
        "Could not reach the server. Check your connection and try again.",
        "network_error",
      );
    }
    return error;
  }
}
