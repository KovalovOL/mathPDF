class ReviewController {
  constructor({ api, userId, onChange, select, onError }) {
    this.#api = api;
    this.#userId = userId;
    this.#onChange = onChange;
    this.#select = select;
    this.#onError = onError;
    this.#states = new Map();
    this.#make = (tag, text, cls) => {
      const e = document.createElement(tag);
      if (text !== undefined) e.textContent = text;
      if (cls) e.className = cls;
      return e;
    };
    this.#storageKey = (id) => `mathpdf-${this.#userId}-review-pending-${id}`;
  }
  #api;
  #userId;
  #onChange;
  #select;
  #onError;
  #states;
  #make;
  #storageKey;
  #pending(id) {
    try {
      const item = JSON.parse(
        localStorage.getItem((0, this.#storageKey)(id)) || "null",
      );
      return item &&
        typeof item.correct === "boolean" &&
        Number.isInteger(item.index) &&
        /^[a-f0-9]{32}$/.test(item.round_id)
        ? item
        : null;
    } catch {
      return null;
    }
  }
  #store(id, value) {
    try {
      value
        ? localStorage.setItem(
            (0, this.#storageKey)(id),
            JSON.stringify({
              schema_version: 1,
              ...value,
            }),
          )
        : localStorage.removeItem((0, this.#storageKey)(id));
    } catch {}
  }
  async #replay(record, state) {
    const item = state.pending || this.#pending(record.id);
    if (!item) return;
    await (0, this.#api)(`/api/reviews/${item.round_id}/answers`, {
      method: "POST",
      body: JSON.stringify({
        index: item.index,
        correct: item.correct,
      }),
    });
    state.pending = null;
    this.#store(record.id, null);
  }
  async #load(record, state, newRound = false, useSaved = false) {
    if (state.loading) return;
    state.loading = true;
    state.error = null;
    try {
      if (!useSaved) await this.#replay(record, state);
      state.data = await (0, this.#api)(
        `/api/study-sets/${record.id}/reviews`,
        {
          method: "POST",
          body: JSON.stringify({
            content: record.data,
            new_round: newRound,
          }),
        },
      );
      if (useSaved) {
        state.pending = null;
        state.conflict = false;
        this.#store(record.id, null);
      }
      if (!state.data.completed_at) {
        const answered = new Set(state.data.answers.map((a) => a.index));
        if (answered.has(record.itemIndex)) {
          record.itemIndex = record.data.items.findIndex(
            (_, i) => !answered.has(i),
          );
          record.flipped = false;
        }
      }
    } catch (error) {
      state.error = error.message;
      state.conflict = error.status === 409;
    } finally {
      state.loading = false;
      (0, this.#onChange)(record);
    }
  }
  #get(record) {
    const key = JSON.stringify(record.data.items);
    let state = this.#states.get(record.id);
    if (!state || state.key !== key) {
      state = {
        key,
        data: null,
        loading: false,
        saving: false,
        error: null,
      };
      this.#states.set(record.id, state);
      this.#load(record, state);
    }
    return state;
  }
  async #grade(record, correct) {
    const state = this.#get(record);
    if (state.loading || state.saving || !state.data) return;
    state.saving = true;
    state.error = null;
    const answer = state.pending || {
      round_id: state.data.id,
      index: record.itemIndex,
      correct,
    };
    state.pending = answer;
    this.#store(record.id, answer);
    (0, this.#onChange)(record);
    try {
      state.data = await (0, this.#api)(
        `/api/reviews/${answer.round_id}/answers`,
        {
          method: "POST",
          body: JSON.stringify({
            index: answer.index,
            correct: answer.correct,
          }),
        },
      );
      state.pending = null;
      this.#store(record.id, null);
      state.saving = false;
      record.reviewBrowse = false;
      if (!state.data.completed_at) {
        const rated = new Set(state.data.answers.map((a) => a.index));
        (0, this.#select)(
          record,
          record.data.items.findIndex((_, i) => !rated.has(i)),
        );
      } else (0, this.#onChange)(record);
    } catch (error) {
      state.saving = false;
      state.error = error.message;
      state.conflict = error.status === 409;
      (0, this.#onChange)(record);
      (0, this.#onError)(error.message);
    }
  }
  #controls(record) {
    const __owner = this;
    const state = __owner.#get(record),
      root = (0, __owner.#make)("section", undefined, "review-controls"),
      status = (0, __owner.#make)("p", undefined, "review-status");
    status.setAttribute("aria-live", "polite");
    root.append(status);
    const actions = (0, __owner.#make)("div", undefined, "review-actions"),
      correct = (0, __owner.#make)("button", "✓ Correct", "review-correct"),
      incorrect = (0, __owner.#make)(
        "button",
        "✕ Incorrect",
        "review-incorrect",
      );
    correct.type = incorrect.type = "button";
    correct.addEventListener("click", () => __owner.#grade(record, true));
    incorrect.addEventListener("click", () => __owner.#grade(record, false));
    actions.append(incorrect, correct);
    root.append(actions);
    function update(flipped) {
      const rated = state.data?.answers.find(
        (a) => a.index === record.itemIndex,
      );
      actions.hidden = !flipped || !!rated || !state.data;
      correct.disabled = incorrect.disabled =
        state.saving || state.loading || !!state.pending;
      status.textContent = state.error
        ? state.error
        : state.saving
          ? "Saving…"
          : state.loading
            ? "Loading progress…"
            : rated
              ? `Marked ${rated.correct ? "correct" : "incorrect"}`
              : "";
      status.hidden = !status.textContent;
      root.hidden = actions.hidden && !status.textContent;
    }
    __owner.#renderReviewError(record, state, root);
    return {
      root,
      update,
    };
  }
  #summary(record) {
    const state = this.#get(record),
      data = state.data;
    if (!data?.completed_at) return null;
    const box = (0, this.#make)("section", undefined, "review-summary");
    box.append(
      (0, this.#make)("span", "Round complete", "review-eyebrow"),
      (0, this.#make)("h2", `${data.score_percent}% correct`),
      (0, this.#make)(
        "p",
        `${data.correct_count} correct · ${data.incorrect_count} incorrect · ${data.item_count} cards`,
      ),
    );
    const previous = data.history.find((r) => r.id !== data.id);
    if (previous) {
      const delta = Number(
        (data.score_percent - previous.score_percent).toFixed(1),
      );
      box.append(
        (0, this.#make)(
          "p",
          `${delta > 0 ? "+" : ""}${delta} percentage points compared with your previous round.`,
          "field-note",
        ),
      );
    }
    this.#renderReviewActions(box, record, state);
    if (state.error) box.append((0, this.#make)("p", state.error, "error"));
    this.#renderReviewHistory(box, data);
    return box;
  }
  get api() {
    return {
      controls: this.#controls.bind(this),
      summary: this.#summary.bind(this),
    };
  }
  #renderReviewError(record, state, root) {
    if (state.error) {
      const retry = (0, this.#make)(
        "button",
        state.conflict
          ? "Use saved progress"
          : state.pending
            ? "Retry saving answer"
            : "Retry progress",
        "small secondary",
      );
      retry.type = "button";
      retry.addEventListener("click", () =>
        state.conflict
          ? this.#load(record, state, false, true)
          : state.pending
            ? this.#grade(record, state.pending.correct)
            : this.#load(record, state),
      );
      root.append(retry);
    }
  }
  #renderReviewHistory(box, data) {
    box.append((0, this.#make)("h3", "Recent progress"));
    const history = (0, this.#make)("ol", undefined, "review-history");
    for (const round of [...data.history.slice(0, 10)].reverse()) {
      const row = (0, this.#make)("li"),
        date = (0, this.#make)(
          "span",
          new Date(round.completed_at).toLocaleDateString("en-GB", {
            day: "numeric",
            month: "short",
          }),
        ),
        bar = (0, this.#make)("progress");
      bar.max = 100;
      bar.value = round.score_percent;
      bar.setAttribute("aria-label", `Round score ${round.score_percent}%`);
      row.append(
        date,
        bar,
        (0, this.#make)("strong", `${round.score_percent}%`),
      );
      history.append(row);
    }
    box.append(history);
  }
  #renderReviewActions(box, record, state) {
    const actions = (0, this.#make)("div", undefined, "review-actions"),
      again = (0, this.#make)(
        "button",
        state.loading ? "Starting…" : "Practice again",
      ),
      browse = (0, this.#make)("button", "Review cards", "secondary");
    again.type = browse.type = "button";
    again.disabled = browse.disabled = state.loading || state.saving;
    again.addEventListener("click", () => {
      record.itemIndex = 0;
      record.flipped = false;
      record.reviewBrowse = false;
      this.#load(record, state, true);
      (0, this.#onChange)(record);
    });
    browse.addEventListener("click", () => {
      record.reviewBrowse = true;
      record.itemIndex = 0;
      record.flipped = false;
      (0, this.#onChange)(record);
    });
    actions.append(again, browse);
    box.append(actions);
  }
}
/* Durable self-assessment is separate from formula rendering and saved study payloads. */
export function createReviewUI({ api, userId, onChange, select, onError }) {
  return new ReviewController({
    api,
    userId,
    onChange,
    select,
    onError,
  }).api;
}
