/** One generation operation owns its deadline, polling and cancellation cleanup. */
export class GenerationFlow {
  #api;
  #ui;
  #timeout;
  #message;
  #accept;
  #limit;
  #finish;
  #controller = new AbortController();
  #jobId;
  #terminal = false;
  #timer;
  #deadline;
  constructor({ api, ui, timeout, message, accept, limit, finish }) {
    this.#api = api;
    this.#ui = ui;
    this.#timeout = timeout;
    this.#message = message;
    this.#accept = accept;
    this.#limit = limit;
    this.#finish = finish;
  }
  get controller() {
    return this.#controller;
  }
  async run(request) {
    this.#start(request);
    try {
      const job = await this.#poll(request);
      await this.#result(job, request);
    } catch (error) {
      if (this.#controller.signal.reason?.name === "AbortError")
        this.#message("Generation cancelled.");
      else if (error.code === "generation_limit") await this.#limit(error);
      else throw error;
    } finally {
      await this.#cleanup();
    }
  }
  #start(request) {
    const ui = this.#ui,
      started = performance.now();
    ui("generation-dialog").close();
    ui("open-generation").disabled = true;
    ui("open-generation").textContent = "Generating…";
    ui("open-generation").setAttribute("aria-busy", "true");
    this.#message("");
    const word = request.mode === "flashcards" ? "flashcard" : "problem";
    ui("generation-progress-label").textContent =
      `Generating ${request.count} ${word}${request.count === 1 ? "" : "s"}…`;
    ui("generation-progress").hidden = false;
    ui("cancel-generation").disabled = false;
    ui("generation-progress-detail").textContent = "Preparing source files…";
    const tick = () => {
      const seconds = Math.floor((performance.now() - started) / 1000);
      ui("generation-elapsed").textContent =
        `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
    };
    tick();
    this.#timer = setInterval(tick, 1000);
    this.#deadline = setTimeout(
      () =>
        this.#controller.abort(
          new Error("Generation timed out. Please try again."),
        ),
      this.#timeout,
    );
  }
  async #poll(request) {
    const options = {
      signal: this.#controller.signal,
      timeoutMs: 15000,
    };
    let job = await this.#api("/api/study/jobs", {
      ...options,
      method: "POST",
      body: JSON.stringify(request),
    });
    this.#jobId = job.id;
    dispatchEvent(new Event("mathpdf-allowance-changed"));
    this.#progress(job);
    while (job.status === "running") {
      await this.#wait();
      job = await this.#api(
        `/api/study/jobs/${encodeURIComponent(this.#jobId)}`,
        options,
      );
      this.#progress(job);
    }
    this.#terminal = true;
    return job;
  }
  #progress(job) {
    const phases = {
      preparing: "Preparing source files",
      generating: "Generating your study set",
      checking: "Finishing your study set",
    };
    this.#ui("generation-progress-detail").textContent =
      `${phases[job.phase] || "Generating"}…`;
  }
  #wait() {
    return new Promise((resolve, reject) => {
      const signal = this.#controller.signal;
      if (signal.aborted) {
        reject(signal.reason);
        return;
      }
      const aborted = () => {
        clearTimeout(wait);
        reject(signal.reason);
      };
      const wait = setTimeout(() => {
        signal.removeEventListener("abort", aborted);
        resolve();
      }, 1200);
      signal.addEventListener("abort", aborted, {
        once: true,
      });
    });
  }
  async #result(job, request) {
    if (job.status === "failed") {
      if (job.limit?.code === "generation_limit")
        throw Object.assign(new Error(job.error), job.limit);
      const reference = /^[a-f0-9]{32}$/.test(job.request_id || "")
        ? ` Reference: ${job.request_id}`
        : "";
      throw new Error(
        (job.error || "Generation failed. Please try again.") + reference,
      );
    }
    if (job.status !== "completed") {
      this.#message("Generation cancelled.");
      return;
    }
    if (job.result.items.length !== request.count)
      throw new Error(
        "The complete requested set was not returned. Please try again.",
      );
    await this.#accept(job.result);
  }
  async #cleanup() {
    clearInterval(this.#timer);
    clearTimeout(this.#deadline);
    if (this.#jobId && !this.#terminal) {
      this.#ui("cancel-generation").disabled = true;
      this.#ui("generation-progress-detail").textContent =
        "Stopping generation…";
      await this.#api(`/api/study/jobs/${encodeURIComponent(this.#jobId)}`, {
        method: "DELETE",
        timeoutMs: 15000,
      }).catch(() => {});
    }
    this.#ui("generation-progress").hidden = true;
    this.#ui("open-generation").setAttribute("aria-busy", "false");
    dispatchEvent(new Event("mathpdf-allowance-changed"));
    this.#finish();
  }
}
