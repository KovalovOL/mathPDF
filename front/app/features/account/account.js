class AccountSession {
  constructor() {
    this.#user = undefined;
    this.#redirecting = false;
    this.#leaveGuard = undefined;
    this.#cancelLeave = undefined;
    this.#uiContextProvider = () => ({});
    this.#lastAction = undefined;
    this.#bindDocumentClick();
    this.#diagnosticCount = 0;
    this.#reporter = import("/static/reports.js")
      .then((module) =>
        module.initialize({
          getUser: () => this.#user,
        }),
      )
      .catch(() => null);
    this.#contextProvider = () => ({});
    this.#reporter.then((r) =>
      r?.setContextProvider(() => (0, this.#contextProvider)()),
    );
    this.#clientBuild =
      document.querySelector('meta[name="mathpdf-build"]')?.content || null;
    this.#newReference = () => crypto.randomUUID().replaceAll("-", "");
    this.#ready = this.#api("/api/me").then((identity) =>
      this.#applyIdentity(identity),
    );
    // Consumers display request failures in their own status region.
    this.#ready.catch(() => {});
    addEventListener("pageshow", (event) => {
      if (event.persisted) location.reload();
    });
    this.#bindDocumentVisibilitychange();
  }
  #user;
  #redirecting;
  #leaveGuard;
  #cancelLeave;
  #uiContextProvider;
  #lastAction;
  #diagnosticCount;
  #reporter;
  #contextProvider;
  #clientBuild;
  #newReference;
  #ready;
  #uiContext() {
    let active = {};
    try {
      active = (0, this.#uiContextProvider)() || {};
    } catch {}
    const context = {
      screen:
        location.pathname === "/workspace"
          ? "workspace"
          : location.pathname === "/admin"
            ? "administration"
            : location.pathname === "/"
              ? "library"
              : "other",
      ...this.#lastAction,
    };
    for (const key of ["document_id", "study_set_id", "file_name"])
      if (typeof active[key] === "string")
        context[key] = active[key].slice(0, 100);
    for (const key of ["page", "item_index"])
      if (Number.isInteger(active[key])) context[key] = active[key];
    return context;
  }
  #routeLabel(path) {
    try {
      const pathname = new URL(path, location.origin).pathname;
      if (pathname.startsWith("/api/")) {
        const label = pathname.replace(/[a-f0-9]{32}|[a-f0-9-]{36}/g, "{id}");
        return /^\/api\/[A-Za-z0-9_/{}/.-]{1,160}$/.test(label)
          ? label
          : "/api/other";
      }
      return ["/", "/workspace", "/login"].includes(pathname)
        ? pathname
        : "/other";
    } catch {
      return "/other";
    }
  }
  #reportFailure(event, path, method, reference, response, receivedBytes) {
    const echoed = response?.headers.get("X-MathPDF-Request-ID");
    const build = response?.headers.get("X-MathPDF-Build");
    const mime = (response?.headers.get("Content-Type") || "")
      .split(";")[0]
      .trim()
      .toLowerCase();
    const length = Number(response?.headers.get("Content-Length") ?? NaN);
    const report = {
      event,
      request_id: /^[a-f0-9]{32}$/.test(echoed || "") ? echoed : reference,
      route: this.#routeLabel(path),
      method: (method || "GET").toUpperCase(),
      status: response?.status || null,
      received_bytes: receivedBytes,
      expected_bytes:
        Number.isSafeInteger(length) && length >= 0 && length <= 104857600
          ? length
          : null,
      content_type: /^[A-Za-z0-9.+/-]{0,80}$/.test(mime) ? mime : "",
      redirected: !!response?.redirected,
      response_route: this.#routeLabel(response?.url || "/other"),
      server_build: /^[a-f0-9]{12}$/.test(build || "") ? build : null,
      client_build: /^[a-f0-9]{12}$/.test(this.#clientBuild || "")
        ? this.#clientBuild
        : null,
    };
    console.error("mathPDF API failure", report);
    if (this.#user && this.#diagnosticCount++ < 10) {
      // Do not use api() here: a failing diagnostic request must never recurse.
      fetch("/api/client-errors", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        keepalive: true,
        headers: {
          "Content-Type": "application/json",
          "X-MathPDF-User": this.#user.id,
          "X-MathPDF-Request-ID": (0, this.#newReference)(),
        },
        body: JSON.stringify(report),
      }).catch(() => {});
    }
    return report.request_id;
  }
  #signIn() {
    if (!this.#redirecting) {
      this.#redirecting = true;
      location.assign(
        `/login?${new URLSearchParams({
          next: location.pathname + location.search,
        })}`,
      );
    }
    const error = new Error("Your session has expired. Sign in to continue.");
    error.status = 401;
    throw error;
  }
  async #request(path, options = {}) {
    const headers = {
      ...options.headers,
    };
    if (!headers["X-MathPDF-Request-ID"])
      headers["X-MathPDF-Request-ID"] = (0, this.#newReference)();
    if (this.#user) headers["X-MathPDF-User"] = this.#user.id;
    if (path.startsWith("/api/"))
      headers["X-MathPDF-UI-Context"] = encodeURIComponent(
        JSON.stringify(this.#uiContext()),
      );
    const response = await fetch(path, {
      ...options,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
    let diagnosticResponse;
    try {
      if (
        path.startsWith("/api/") &&
        (response.status >= 400 ||
          (response.headers.get("content-type") || "").includes("json"))
      )
        diagnosticResponse = response.clone();
    } catch {}
    if (diagnosticResponse)
      this.#reporter
        .then((r) => r?.observe(path, options, diagnosticResponse))
        .catch(() => {});
    if (response.status === 401) this.#signIn();
    if (response.headers.get("X-MathPDF-Account-Changed") === "1") {
      location.assign("/");
      throw new Error(
        "The active account has changed. Reopening your library.",
      );
    }
    return response;
  }
  async #api(path, options = {}) {
    const { JsonApiCall } = await import("/static/json-api-call.js");
    return new JsonApiCall({
      request: this.#request.bind(this),
      report: this.#reportFailure.bind(this),
      reference: this.#newReference,
      routeLabel: this.#routeLabel.bind(this),
      signIn: this.#signIn.bind(this),
    }).execute(path, options);
  }
  #bindDocumentClick() {
    document.addEventListener(
      "click",
      (event) => {
        const target = event.target.closest("button,a,summary");
        if (target)
          this.#lastAction = {
            action: (
              target.getAttribute("aria-label") || target.textContent.trim()
            ).slice(0, 80),
            target: target.id || target.tagName.toLowerCase(),
          };
      },
      true,
    );
  }
  #bindDocumentVisibilitychange() {
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && this.#user) this.#api("/api/me").catch(() => {});
    });
  }
  get api() {
    const __owner = this;
    return {
      api: __owner.#api.bind(__owner),
      request: __owner.#request.bind(__owner),
      ready: __owner.#ready,
      setUIContextProvider: (...args) =>
        __owner.#api_setUIContextProvider(...args),
      setContextProvider: (...args) => __owner.#api_setContextProvider(...args),
      setLeaveGuard: (...args) => __owner.#api_setLeaveGuard(...args),
      get user() {
        return __owner.#user;
      },
    };
  }
  #api_setUIContextProvider(provider) {
    return (this.#uiContextProvider = provider);
  }
  #api_setContextProvider(provider) {
    return (this.#contextProvider = provider);
  }
  #api_setLeaveGuard(guard, cancel) {
    this.#leaveGuard = guard;
    this.#cancelLeave = cancel;
  }
  #showWelcome(identity) {
    if (
      !identity.welcome_pending ||
      !["/", "/workspace"].includes(location.pathname)
    )
      return;
    import("/static/welcome.js")
      .then((module) => module.showWelcome({ api: this.#api.bind(this) }))
      .catch(() => {});
  }
  #applyIdentity(identity) {
    this.#user = identity;
    this.#showWelcome(identity);
    const container = document.getElementById("account");
    if (container) {
      const [menu, summary] = this.#createAccountHeader();
      const [form, panel] = this.#createLogoutForm(menu);
      const role = document.createElement("span");
      role.className = "account-role";
      role.textContent = (this.#user.role || "free").replace(/^./, (c) =>
        c.toUpperCase(),
      );
      panel.append(role);
      if (["admin", "owner"].includes(this.#user.role)) {
        const admin = document.createElement("a");
        admin.href = "/admin";
        admin.textContent = "Administration";
        panel.append(admin);
      }
      this.#reporter.then((r) => {
        if (r) {
          const feedback = r.button();
          feedback.addEventListener("click", () => (menu.open = false));
          panel.insertBefore(feedback, form);
        }
      });
      panel.append(form);
      menu.append(summary, panel);
      container.replaceChildren(menu);
      document.addEventListener("click", (event) => {
        if (!menu.contains(event.target)) menu.open = false;
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          menu.open = false;
          summary.focus();
        }
      });
    }
    import("/static/allowance-ui.js")
      .then((module) =>
        module
          .createAllowanceUI({
            api: this.#api.bind(this),
          })
          .refresh(),
      )
      .catch(() => {});
    return this.#user;
  }
  #bindLogout(form, logout, logoutError, menu) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      logout.disabled = true;
      logoutError.hidden = true;
      let logoutTimer;
      try {
        if (this.#leaveGuard && !(await (0, this.#leaveGuard)())) return;
        const controller = new AbortController();
        logoutTimer = setTimeout(() => controller.abort(), 15000);
        const response = await this.#request("/auth/logout", {
          method: "POST",
          signal: controller.signal,
        });
        if (!response.ok)
          throw new Error("Could not sign out. Please try again.");
        try {
          await (
            await import("/static/visual-cache.js")
          ).clearVisualCache(this.#user.id);
        } catch {}
        location.assign("/login");
      } catch (error) {
        this.#cancelLeave?.();
        logoutError.textContent =
          error.name === "AbortError"
            ? "Sign-out timed out. Please try again."
            : error.message;
        logoutError.hidden = false;
        menu.open = true;
      } finally {
        clearTimeout(logoutTimer);
        logout.disabled = false;
      }
    });
  }
  #createLogoutForm(menu) {
    const panel = document.createElement("div");
    panel.className = "account-panel";
    const name = document.createElement("strong");
    name.textContent = this.#user.name;
    const email = document.createElement("span");
    email.className = "account-email";
    email.textContent = this.#user.email;
    const form = document.createElement("form");
    form.method = "post";
    form.action = "/auth/logout";
    const logout = document.createElement("button");
    logout.type = "submit";
    logout.className = "secondary";
    logout.textContent = "Sign out";
    const logoutError = document.createElement("p");
    logoutError.className = "error";
    logoutError.hidden = true;
    logoutError.setAttribute("role", "alert");
    this.#bindLogout(form, logout, logoutError, menu);
    form.append(logout, logoutError);
    panel.append(name, email);
    return [form, panel];
  }
  #createAccountHeader() {
    const menu = document.createElement("details");
    menu.className = "account-menu";
    const summary = document.createElement("summary");
    summary.setAttribute("aria-label", `Account: ${this.#user.email}`);
    const avatar = document.createElement("span");
    avatar.className = "account-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = this.#user.name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => [...part][0])
      .join("")
      .toUpperCase();
    const label = document.createElement("span");
    label.className = "account-label";
    label.textContent = this.#user.name;
    summary.append(avatar, label);
    return [menu, summary];
  }
}
/* Shared identity and authenticated requests for the library and workspace. */
window.MathPDFSession = new AccountSession().api;
