class AdministrationController {
  constructor() {
    this.#$ = (id) => document.getElementById(id);
    this.#api = window.MathPDFSession.api;
    this.#number = (n) => Number(n || 0).toLocaleString();
    this.#money = (n) =>
      new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 6,
      }).format(Number(n || 0));
    this.#date = (value) => (value ? new Date(value).toLocaleString() : "—");
    this.#node = (tag, text, cls) => {
      const e = document.createElement(tag);
      if (text !== undefined) e.textContent = text;
      if (cls) e.className = cls;
      return e;
    };
    this.#button = (text, fn) => {
      const b = (0, this.#node)("button", text, "small secondary");
      b.type = "button";
      b.addEventListener("click", () => this.#run(fn));
      return b;
    };
    this.#user = undefined;
    this.#days = 7;
    this.#tab = "overview";
    this.#offset = 0;
    this.#query = "";
    this.#users = [];
    this.#reports = [];
    this.#reportOffset = 0;
    this.#bindDataTabClick();
    this.#bindDataDaysClick();
    this.#bindAdminRefreshClick();
    this.#bindAdminDetailCloseClick();
    this.#bindUserSearchSubmit();
    this.#bindUsersPreviousClick();
    this.#bindUsersNextClick();
    this.#bindReportFilterChange();
    this.#bindReportsPreviousClick();
    this.#bindReportsNextClick();
    this.#bindPriceFormSubmit();
    this.#bindDefaultAllowanceFormSubmit();
    window.MathPDFSession.ready.then((identity) => {
      this.#user = identity;
      return this.#run(this.#load.bind(this));
    });
  }
  #$;
  #api;
  #number;
  #money;
  #date;
  #node;
  #button;
  #user;
  #days;
  #tab;
  #offset;
  #query;
  #users;
  #reports;
  #reportOffset;
  async #run(fn) {
    (0, this.#$)("admin-error").hidden = true;
    try {
      await fn();
    } catch (error) {
      (0, this.#$)("admin-error").textContent = error.message;
      (0, this.#$)("admin-error").hidden = false;
    }
  }
  #table(target, headers, rows) {
    const t = (0, this.#node)("table", undefined, "admin-table"),
      head = (0, this.#node)("thead"),
      tr = (0, this.#node)("tr");
    headers.forEach((h) => tr.append((0, this.#node)("th", h)));
    head.append(tr);
    t.append(head);
    const body = (0, this.#node)("tbody");
    for (const values of rows) {
      const row = (0, this.#node)("tr");
      for (const value of values) {
        const td = (0, this.#node)("td");
        value instanceof Node
          ? td.append(value)
          : (td.textContent = value ?? "—");
        row.append(td);
      }
      body.append(row);
    }
    t.append(body);
    target.replaceChildren(t);
    if (!rows.length)
      target.append(
        (0, this.#node)("p", "No records in this view.", "field-note"),
      );
  }
  #stats(target, entries) {
    target.replaceChildren(
      ...entries.map(([label, value, note]) => {
        const card = (0, this.#node)("div", undefined, "admin-stat");
        card.append(
          (0, this.#node)("span", label),
          (0, this.#node)("strong", value),
        );
        if (note) card.append((0, this.#node)("small", note));
        return card;
      }),
    );
  }
  #detail(title) {
    (0, this.#$)("admin-detail-heading").textContent = title;
    (0, this.#$)("admin-detail-body").replaceChildren();
    if (!(0, this.#$)("admin-detail").open)
      (0, this.#$)("admin-detail").showModal();
    return (0, this.#$)("admin-detail-body");
  }
  #summary(t) {
    return [
      [
        "AI requests",
        (0, this.#number)(t.requests),
        `${(0, this.#number)(t.average_requests_per_day)} / day`,
      ],
      [
        "Reported tokens",
        (0, this.#number)(t.total_tokens),
        `${(0, this.#number)(t.average_tokens_per_day)} / day`,
      ],
      [
        "Estimated cost",
        (0, this.#money)(t.estimated_cost_usd),
        `${(0, this.#money)(t.average_cost_usd_per_day)} / day`,
      ],
      [
        "Incomplete accounting",
        (0, this.#number)(t.unknown_usage_requests),
        `${(0, this.#number)(t.unpriced_requests)} requests without a known cost`,
      ],
    ];
  }
  async #overview() {
    const [counts, usage, people, limits] = await Promise.all([
      (0, this.#api)("/api/admin/overview"),
      (0, this.#api)(`/api/admin/usage?days=${this.#days}`),
      (0, this.#api)("/api/admin/users"),
      (0, this.#api)("/api/admin/generation-limits"),
    ]);
    this.#users = people;
    (0, this.#$)("default-allowance").value = limits.daily_tokens;
    this.#stats((0, this.#$)("admin-counts"), [
      ["Users", (0, this.#number)(counts.users)],
      ...counts.roles.map((r) => [r.role, (0, this.#number)(r.count)]),
      [
        "Open reports",
        (0, this.#number)(
          counts.reports
            .filter((r) => r.status !== "resolved")
            .reduce((n, r) => n + r.count, 0),
        ),
      ],
    ]);
    (0, this.#$)("usage-note").textContent =
      `UTC calendar days, including today. Daily averages include days with no requests. ${counts.history_note}`;
    this.#stats((0, this.#$)("usage-totals"), this.#summary(usage.totals));
    this.#renderUsageTables(usage);
  }
  async #userList() {
    this.#users = await (0, this.#api)(
      `/api/admin/users?${new URLSearchParams({
        q: this.#query,
        offset: this.#offset,
      })}`,
    );
    this.#table(
      (0, this.#$)("user-list"),
      ["User", "Role", "Files", "Study sets", "Joined", "Latest saved action"],
      this.#users.map((u) => [
        (0, this.#button)(`${u.name} · ${u.email}`, () =>
          this.#userDetail(u.id),
        ),
        u.role,
        (0, this.#number)(u.file_count),
        (0, this.#number)(u.set_count),
        (0, this.#date)(u.created_at),
        (0, this.#date)(u.last_activity),
      ]),
    );
    (0, this.#$)("users-previous").disabled = this.#offset === 0;
    (0, this.#$)("users-next").disabled = this.#users.length < 200;
    (0, this.#$)("users-page").textContent = `Page ${this.#offset / 200 + 1}`;
  }
  async #userDetail(id) {
    const result = await (0, this.#api)(`/api/admin/users/${id}`),
      p = result.user,
      body = this.#detail(p.name);
    body.append(
      (0, this.#node)("p", p.email),
      (0, this.#node)(
        "p",
        `Joined ${(0, this.#date)(p.created_at)} · Last sign-in ${(0, this.#date)(p.updated_at)}`,
        "field-note",
      ),
    );
    this.#renderRoleControl(body, p, id);
    this.#renderUserAllowance(body, result, id);
    this.#renderUserPeriods(body, result);
    this.#renderUserDocuments(body, result);
  }
  #reportList() {
    const filtered = this.#reports.filter(
      (r) =>
        !(0, this.#$)("report-filter").value ||
        r.status === (0, this.#$)("report-filter").value,
    );
    this.#table(
      (0, this.#$)("report-list"),
      ["Created", "User", "Issue", "Comment", "Status", "Context"],
      filtered.map((r) => [
        (0, this.#button)((0, this.#date)(r.created_at), () =>
          this.#reportDetail(r.id),
        ),
        r.email,
        `${r.origin} · ${r.category}`,
        r.comment.slice(0, 180),
        r.status,
        r.collection_status,
      ]),
    );
  }
  async #reportPage() {
    this.#reports = await (0, this.#api)(
      `/api/admin/reports?offset=${this.#reportOffset}${(0, this.#$)("report-filter").value ? "&status=" + (0, this.#$)("report-filter").value : ""}`,
    );
    this.#reportList();
    (0, this.#$)("reports-previous").disabled = this.#reportOffset === 0;
    (0, this.#$)("reports-next").disabled = this.#reports.length < 100;
    (0, this.#$)("reports-page").textContent =
      `Page ${this.#reportOffset / 100 + 1}`;
  }
  async #reportDetail(id) {
    const r = await (0, this.#api)(`/api/admin/reports/${id}`),
      body = this.#detail(`Report ${id.slice(0, 8)}`);
    body.append(
      (0, this.#node)(
        "p",
        `${r.origin} · ${r.category} · ${(0, this.#date)(r.created_at)}`,
        "field-note",
      ),
      (0, this.#node)("p", r.comment || "No comment supplied."),
    );
    const [status] = this.#renderTriageControls(body, r, id);
    this.#renderTriageNote(body, r, id, status);
    this.#renderIncidentSummary(body, r);
    this.#renderReportTimeline(body, r.summary || {});
    this.#renderReportEvidence(body, r);
  }
  async #prices() {
    const items = await (0, this.#api)("/api/admin/prices");
    this.#table(
      (0, this.#$)("price-list"),
      [
        "Provider / model",
        "Input",
        "Cached",
        "Output",
        "Effective UTC",
        "Source",
      ],
      items.map((p) => {
        let source;
        try {
          const url = new URL(p.source);
          if (!["https:", "http:"].includes(url.protocol)) throw new Error();
          source = (0, this.#node)("a", "Price source");
          source.href = url.href;
          source.target = "_blank";
          source.rel = "noopener noreferrer";
        } catch {
          source = p.source;
        }
        return [
          `${p.provider} / ${p.model}`,
          p.input_per_million,
          p.cached_per_million,
          p.output_per_million,
          (0, this.#date)(p.effective_at),
          source,
        ];
      }),
    );
    (0, this.#$)("price-form").hidden = this.#user.role !== "owner";
  }
  async #load() {
    (0, this.#$)("admin-status").textContent = "Loading…";
    try {
      if (this.#tab === "overview") await this.#overview();
      if (this.#tab === "users") await this.#userList();
      if (this.#tab === "reports") await this.#reportPage();
      if (this.#tab === "prices") await this.#prices();
    } finally {
      (0, this.#$)("admin-status").textContent =
        `Updated ${new Date().toLocaleTimeString()}`;
    }
  }
  #bindDataTabClick() {
    document.querySelectorAll("[data-tab]").forEach((b) =>
      b.addEventListener("click", () =>
        this.#run(async () => {
          this.#tab = b.dataset.tab;
          document
            .querySelectorAll("[data-tab]")
            .forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
          for (const name of ["overview", "users", "reports", "prices"])
            (0, this.#$)(`admin-${name}`).hidden = name !== this.#tab;
          await this.#load();
        }),
      ),
    );
  }
  #bindDataDaysClick() {
    document.querySelectorAll("[data-days]").forEach((b) =>
      b.addEventListener("click", () =>
        this.#run(async () => {
          this.#days = Number(b.dataset.days);
          document
            .querySelectorAll("[data-days]")
            .forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
          await this.#overview();
        }),
      ),
    );
  }
  #bindAdminRefreshClick() {
    (0, this.#$)("admin-refresh").addEventListener("click", () =>
      this.#run(this.#load.bind(this)),
    );
  }
  #bindAdminDetailCloseClick() {
    (0, this.#$)("admin-detail-close").addEventListener("click", () =>
      (0, this.#$)("admin-detail").close(),
    );
  }
  #bindUserSearchSubmit() {
    (0, this.#$)("user-search").addEventListener("submit", (e) => {
      e.preventDefault();
      this.#query = (0, this.#$)("user-query").value;
      this.#offset = 0;
      this.#run(this.#userList.bind(this));
    });
  }
  #bindUsersPreviousClick() {
    (0, this.#$)("users-previous").addEventListener("click", () => {
      this.#offset = Math.max(0, this.#offset - 200);
      this.#run(this.#userList.bind(this));
    });
  }
  #bindUsersNextClick() {
    (0, this.#$)("users-next").addEventListener("click", () => {
      this.#offset += 200;
      this.#run(this.#userList.bind(this));
    });
  }
  #bindReportFilterChange() {
    (0, this.#$)("report-filter").addEventListener("change", () => {
      this.#reportOffset = 0;
      this.#run(this.#reportPage.bind(this));
    });
  }
  #bindReportsPreviousClick() {
    (0, this.#$)("reports-previous").addEventListener("click", () => {
      this.#reportOffset = Math.max(0, this.#reportOffset - 100);
      this.#run(this.#reportPage.bind(this));
    });
  }
  #bindReportsNextClick() {
    (0, this.#$)("reports-next").addEventListener("click", () => {
      this.#reportOffset += 100;
      this.#run(this.#reportPage.bind(this));
    });
  }
  #bindPriceFormSubmit() {
    (0, this.#$)("price-form").addEventListener("submit", (e) => {
      e.preventDefault();
      this.#run(async () => {
        const data = Object.fromEntries(new FormData(e.target));
        if (
          !confirm(
            `Add a new tariff for ${data.model}? Existing request costs will stay unchanged.`,
          )
        )
          return;
        await (0, this.#api)("/api/admin/prices", {
          method: "POST",
          body: JSON.stringify(data),
        });
        e.target.reset();
        await this.#prices();
      });
    });
  }
  #bindDefaultAllowanceFormSubmit() {
    (0, this.#$)("default-allowance-form").addEventListener(
      "submit",
      (event) => {
        event.preventDefault();
        this.#run(async () => {
          const save = event.target.querySelector("button");
          save.disabled = true;
          try {
            await (0, this.#api)("/api/admin/generation-limits", {
              method: "PATCH",
              body: JSON.stringify({
                daily_tokens: Number((0, this.#$)("default-allowance").value),
              }),
            });
            await this.#overview();
          } finally {
            save.disabled = false;
          }
        });
      },
    );
  }
  #renderUsageTables(usage) {
    this.#renderUsageChart(usage);
    this.#table(
      (0, this.#$)("usage-users"),
      [
        "User",
        "Requests",
        "Tokens",
        "Tokens / day",
        "Estimated USD",
        "Unknown cost",
      ],
      usage.users.map((r) => [
        (0, this.#button)(
          this.#users.find((u) => u.id === r.user_id)?.email || r.user_id,
          () => this.#userDetail(r.user_id),
        ),
        (0, this.#number)(r.requests),
        (0, this.#number)(r.total_tokens),
        (0, this.#number)(r.average_tokens_per_day),
        (0, this.#money)(r.estimated_cost_usd),
        (0, this.#number)(r.unpriced_requests),
      ]),
    );
    this.#table(
      (0, this.#$)("usage-models"),
      ["Model", "Requests", "Input", "Cached input", "Output", "Estimated USD"],
      usage.models.map((r) => [
        r.model,
        (0, this.#number)(r.requests),
        (0, this.#number)(r.input_tokens),
        (0, this.#number)(r.cached_tokens),
        (0, this.#number)(r.output_tokens),
        (0, this.#money)(r.estimated_cost_usd),
      ]),
    );
  }
  #renderUserDocuments(body, result) {
    body.append((0, this.#node)("h3", `Files (${result.files.length})`));
    const files = (0, this.#node)("div", undefined, "admin-table-wrap");
    this.#table(
      files,
      ["Name", "Pages", "Bytes"],
      result.files.map((f) => [
        f.filename,
        f.page_count ?? "—",
        (0, this.#number)(f.size),
      ]),
    );
    body.append(
      files,
      (0, this.#node)("h3", `Study sets (${result.sets.length})`),
    );
    const sets = (0, this.#node)("div", undefined, "admin-table-wrap");
    this.#table(
      sets,
      ["Title", "Mode", "Items"],
      result.sets.map((s) => [
        s.title,
        s.mode,
        (0, this.#number)(s.item_count),
      ]),
    );
    body.append(sets);
  }
  #renderUserPeriods(body, result) {
    for (const period of [1, 7, 30]) {
      body.append(
        (0, this.#node)(
          "h3",
          `${period === 1 ? "Today" : `Last ${period} days`} · UTC`,
        ),
      );
      const cards = (0, this.#node)("div", undefined, "admin-stats");
      this.#stats(cards, this.#summary(result.usage[String(period)].totals));
      body.append(cards);
      const models = (0, this.#node)("div", undefined, "admin-table-wrap");
      this.#table(
        models,
        ["Model", "Requests", "Tokens", "Estimated USD"],
        result.usage[String(period)].models.map((m) => [
          m.model,
          (0, this.#number)(m.requests),
          (0, this.#number)(m.total_tokens),
          (0, this.#money)(m.estimated_cost_usd),
        ]),
      );
      body.append(models);
    }
  }
  #renderUserAllowance(body, result, id) {
    const allowance = result.allowance;
    if (allowance) {
      const limits = (0, this.#node)("form", undefined, "admin-allowance-form"),
        label = (0, this.#node)("label", "Daily token override"),
        input = (0, this.#node)("input");
      input.type = "number";
      input.min = "0";
      input.max = "1000000000";
      input.step = "1";
      input.placeholder = `Default: ${allowance.default_daily_tokens}`;
      input.value = allowance.override_daily_tokens ?? "";
      label.append(input);
      const save = (0, this.#node)("button", "Save allowance");
      save.type = "submit";
      limits.append(
        label,
        save,
        (0, this.#node)(
          "p",
          `${allowance.limited ? "Free plan" : "Unlimited role"} · ${(0, this.#number)(allowance.used_tokens)} actual tokens · ${(0, this.#number)(allowance.reserved_tokens)} pending. Leave empty to use the default.`,
          "field-note",
        ),
      );
      limits.addEventListener("submit", (event) => {
        event.preventDefault();
        this.#run(async () => {
          save.disabled = true;
          try {
            await (0, this.#api)(`/api/admin/users/${id}/generation-limit`, {
              method: "PATCH",
              body: JSON.stringify({
                daily_tokens: input.value === "" ? null : Number(input.value),
              }),
            });
            await this.#userDetail(id);
          } finally {
            save.disabled = false;
          }
        });
      });
      body.append(limits);
    }
  }
  #renderRoleControl(body, p, id) {
    const controls = (0, this.#node)("div", undefined, "admin-section-heading");
    controls.append((0, this.#node)("strong", `Role: ${p.role}`));
    if (this.#user.role === "owner" && p.role !== "owner") {
      const select = (0, this.#node)("select");
      select.setAttribute("aria-label", "User role");
      for (const r of ["free", "premium", "admin"])
        select.append(new Option(r, r));
      select.value = p.role;
      controls.append(
        select,
        (0, this.#button)("Update role", async () => {
          if (!confirm(`Change ${p.email} from ${p.role} to ${select.value}?`))
            return;
          await (0, this.#api)(`/api/admin/users/${id}/role`, {
            method: "PATCH",
            body: JSON.stringify({
              role: select.value,
            }),
          });
          await this.#userDetail(id);
        }),
      );
    }
    body.append(controls);
  }
  #renderReportEvidence(body, r) {
    const advanced = (0, this.#node)("details", undefined, "incident-advanced");
    advanced.append(
      (0, this.#node)("summary", "Advanced: full diagnostic JSON"),
      (0, this.#node)(
        "p",
        "Original evidence is retained for deeper investigation.",
        "field-note",
      ),
      (0, this.#node)(
        "pre",
        JSON.stringify(
          {
            request_id: r.request_id,
            user_id: r.user_id,
            context: r.payload,
            manifest: r.manifest,
          },
          null,
          2,
        ),
        "admin-context",
      ),
    );
    body.append(advanced);
  }
  #renderReportTimeline(body, incident) {
    if (incident.timeline?.length) {
      body.append((0, this.#node)("h3", "Request timeline"));
      const timeline = (0, this.#node)("div", undefined, "admin-table-wrap");
      this.#table(
        timeline,
        ["Request", "HTTP", "Count", "Duration"],
        incident.timeline.map((t) => [
          `${t.method || ""} ${t.route}`,
          t.status ?? "—",
          t.count || 1,
          t.duration_ms !== null ? `${t.duration_ms} ms` : "—",
        ]),
      );
      body.append(timeline);
    }
  }
  #renderIncidentSummary(body, r) {
    const incident = r.summary || {},
      overview = (0, this.#node)("section", undefined, "incident-summary");
    overview.append((0, this.#node)("h3", incident.title || "Report details"));
    if (incident.error_code)
      overview.append(
        (0, this.#node)("code", incident.error_code, "incident-code"),
      );
    this.#renderIncidentFields(overview, incident, r);
    if (incident.documents?.length) {
      overview.append((0, this.#node)("h4", "Referenced files"));
      const files = (0, this.#node)("ul");
      for (const file of incident.documents)
        files.append((0, this.#node)("li", file.name || file.id));
      overview.append(files);
    }
    if (incident.steps?.length) {
      overview.append((0, this.#node)("h4", "Recent actions"));
      const steps = (0, this.#node)("ol", undefined, "incident-steps");
      for (const step of incident.steps)
        steps.append((0, this.#node)("li", step.action || "Interaction"));
      overview.append(steps);
    }
    body.append(overview);
  }
  #renderTriageNote(body, r, id, status) {
    const label = (0, this.#node)("label", "Internal note"),
      note = (0, this.#node)("textarea");
    note.rows = 3;
    note.maxLength = 5000;
    note.value = r.note;
    label.append(note);
    body.append(
      label,
      (0, this.#button)("Save triage", async () => {
        await (0, this.#api)(`/api/admin/reports/${id}`, {
          method: "PATCH",
          body: JSON.stringify({
            status: status.value,
            note: note.value,
          }),
        });
        await this.#reportDetail(id);
      }),
      (0, this.#node)("h3", "Incident summary"),
    );
  }
  #renderTriageControls(body, r, id) {
    const controls = (0, this.#node)("div", undefined, "admin-section-heading"),
      status = (0, this.#node)("select");
    status.setAttribute("aria-label", "Report status");
    ["new", "investigating", "resolved"].forEach((v) =>
      status.append(new Option(v, v)),
    );
    status.value = r.status;
    controls.append(status);
    const download = (0, this.#node)(
      "a",
      "Download private bundle",
      "admin-download",
    );
    download.href = `/api/admin/reports/${id}/bundle`;
    if (r.collection_status === "ready") controls.append(download);
    else
      controls.append(
        (0, this.#node)(
          "span",
          `Context: ${r.collection_status}. Refresh to check again.`,
          "field-note",
        ),
      );
    body.append(controls);
    return [status];
  }
  #renderUsageChart(usage) {
    const max = Math.max(1, ...usage.daily.map((d) => d.total_tokens));
    (0, this.#$)("usage-chart").replaceChildren(
      ...usage.daily.map((d) => {
        const c = (0, this.#node)("div", undefined, "admin-bar-column"),
          b = (0, this.#node)("div", undefined, "admin-bar");
        b.style.height = `${Math.max(1, (d.total_tokens / max) * 130)}px`;
        c.title = `${d.date}: ${(0, this.#number)(d.total_tokens)} tokens, ${(0, this.#number)(d.requests)} requests, ${(0, this.#money)(d.estimated_cost_usd)}`;
        c.append(
          (0, this.#node)("small", (0, this.#number)(d.total_tokens)),
          b,
          (0, this.#node)("small", d.date.slice(5)),
        );
        return c;
      }),
    );
  }
  #renderIncidentFields(overview, incident, r) {
    const fields = (0, this.#node)("dl", undefined, "incident-fields");
    for (const [label, value] of [
      ["User", r.payload?.user?.email || r.user_id],
      ["Screen", incident.screen],
      ["Action", incident.action],
      [
        "Request",
        [
          incident.method,
          incident.route,
          incident.status ? "HTTP " + incident.status : null,
        ]
          .filter(Boolean)
          .join(" · "),
      ],
      ["Error type", incident.error_type],
      ["Location", incident.location],
      ["PDF page", incident.page],
      [
        "Card",
        Number.isInteger(incident.item_index) ? incident.item_index + 1 : null,
      ],
      ["Reference", r.request_id],
    ]) {
      if (value !== null && value !== undefined && value !== "") {
        fields.append(
          (0, this.#node)("dt", label),
          (0, this.#node)("dd", String(value)),
        );
      }
    }
    overview.append(fields);
  }
}
/* Administration reads dedicated, session- and role-protected service endpoints. */
new AdministrationController();
