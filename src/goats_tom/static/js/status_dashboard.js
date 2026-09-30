/**
 * An error with a code, so callers need not match on its message.
 */
class StatusError extends Error {
  /**
   * @param {string} message - What to show.
   * @param {string} [code="error"] - What went wrong, e.g. "session" or "timeout".
   */
  constructor(message, code = "error") {
    super(message);
    this.code = code;
  }
}

/**
 * StatusDashboard checks every external service GOATS relies on and shows the results in
 * two tables: the user's accounts, and services used without credentials.
 *
 * Requires `utils.js`.
 */
class StatusDashboard {
  /** Milliseconds before a single check is given up on. */
  static REQUEST_TIMEOUT_MS = 35000;

  /** How many services are checked at once. */
  static CONCURRENCY = 6;

  /**
   * Label and badge classes of each service status. Subtle badges, so a page of healthy
   * services is not a wall of colour, and no red: an outage elsewhere is not a GOATS fault.
   */
  static STATUS = {
    ok: ["Available", "bg-success-subtle text-success-emphasis border border-success-subtle"],
    down: [
      "Not available",
      "bg-warning-subtle text-warning-emphasis border border-warning-subtle",
    ],
    unknown: [
      "Unknown",
      "bg-secondary-subtle text-secondary-emphasis border border-secondary-subtle",
    ],
  };

  /** Label, text colour and icon of each state of the stored credentials. */
  static ACCESS = {
    verified: ["Verified", "", "fa-circle-check text-success"],
    rejected: ["Rejected", "text-warning-emphasis", "fa-circle-xmark"],
    missing: ["Not configured", "text-warning-emphasis", "fa-circle-exclamation"],
    unverifiable: ["Not verifiable", "text-body-secondary", "fa-circle-minus"],
    unchecked: ["Not checked", "text-body-secondary", "fa-circle-question"],
  };

  /** Heading of each group of services, in display order. */
  static SECTIONS = [
    ["account", "Your accounts"],
    ["public", "Other services"],
  ];

  /**
   * Build the dashboard and start checking every service.
   * @param {HTMLElement} parent - Element to render the dashboard into.
   * @param {Object} [options]
   * @param {string} [options.username="you"] - Whose credentials are checked.
   */
  constructor(parent, { username = "you" } = {}) {
    this.parent = parent;
    this.username = username;
    this.rows = new Map();
    this.loaded = false;
    this.refreshing = false;
    this.build();
    this.ready = this.refreshAll();
  }

  /**
   * Create an element with classes and text.
   * @param {string} tag - The tag name.
   * @param {string} [className=""] - Space-separated class names.
   * @param {string} [text=""] - Its text content.
   * @returns {HTMLElement} The element.
   */
  element(tag, className = "", text = "") {
    const element = Utils.createElement(tag, className.split(" ").filter(Boolean));
    element.textContent = text;
    return element;
  }

  /**
   * Replace an element's content with a Font Awesome icon. A fresh <i> each time: Font
   * Awesome's JS swaps rendered ones for an <svg>.
   * @param {HTMLElement} target - Where the icon goes.
   * @param {string} iconClass - The icon's classes, e.g. "fa-pencil".
   * @param {boolean} [spin=false] - Whether it spins.
   */
  setIcon(target, iconClass, spin = false) {
    target.replaceChildren(this.icon(`${iconClass}${spin ? " fa-spin" : ""}`));
  }

  /**
   * Create a decorative Font Awesome icon.
   * @param {string} iconClass - The icon's classes.
   * @returns {HTMLElement} The icon, hidden from screen readers.
   */
  icon(iconClass) {
    const icon = this.element("i", `fa-solid ${iconClass}`);
    icon.setAttribute("aria-hidden", "true");
    return icon;
  }

  /** Render the toolbar, the warning and the empty sections. */
  build() {
    this.bar = this.element(
      "div",
      "d-flex flex-wrap justify-content-between align-items-center gap-3 py-2 px-3 mb-4 " +
        "border-start border-3 border-primary bg-body-secondary rounded-end",
    );
    // The page's only live region, so a screen reader hears one summary, once checked.
    this.summary = this.element("p", "mb-0 fw-semibold");
    this.summary.setAttribute("role", "status");
    this.refresh = this.element("button", "btn btn-primary", "Refresh all");
    this.refresh.type = "button";
    this.refresh.addEventListener("click", () => this.refreshAll({ refresh: true }));
    this.bar.append(this.summary, this.refresh);
    // A warning, not an error: an outage elsewhere does not mean GOATS is broken.
    this.notice = this.element("div", "alert alert-warning");
    this.notice.hidden = true;
    this.sections = this.element("div");
    this.parent.replaceChildren(this.bar, this.notice, this.sections);
  }

  /**
   * Fetch JSON from GOATS, giving up after `REQUEST_TIMEOUT_MS`.
   * @param {string} url - The URL to request.
   * @returns {Promise<Object>} The parsed response.
   * @throws {StatusError} If the session expired, the request timed out or GOATS failed.
   */
  async requestJSON(url) {
    const controller = new AbortController();
    let timer;
    const deadline = new Promise((_, reject) => {
      timer = setTimeout(() => {
        reject(new StatusError("The check timed out. Please try again.", "timeout"));
        controller.abort();
      }, StatusDashboard.REQUEST_TIMEOUT_MS);
    });
    const request = async () => {
      const response = await fetch(url, { signal: controller.signal });
      // An expired session is redirected to the login page, not refused.
      if (response.status === 401 || response.status === 403 || response.redirected) {
        throw new StatusError(
          "Your session has expired or access was denied. Sign in again and retry.",
          "session",
        );
      }
      if (!response.ok) {
        throw new StatusError("GOATS could not complete the request. Please retry.");
      }
      try {
        return await response.json();
      } catch {
        throw new StatusError("GOATS returned an unexpected response. Please retry.");
      }
    };
    try {
      return await Promise.race([request(), deadline]);
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * Whether the service list from the API has the shape the dashboard expects.
   * @param {Object} data - The parsed response.
   * @returns {boolean} `true` if it can be rendered.
   */
  static isServiceList(data) {
    const isService = (s) =>
      s &&
      typeof s.name === "string" &&
      typeof s.display_name === "string" &&
      ["account", "public"].includes(s.group) &&
      typeof s.endpoint === "string" &&
      /^\/status\/[a-z0-9-]+\/$/.test(s.endpoint);
    return (
      Array.isArray(data?.services) &&
      data.services.length > 0 &&
      data.services.every(isService) &&
      new Set(data.services.map((s) => s.name)).size === data.services.length
    );
  }

  /** Load the list of services and render a table per section. */
  async loadServices() {
    const data = await this.requestJSON("/api/status/");
    if (!StatusDashboard.isServiceList(data)) {
      throw new StatusError("GOATS returned an unexpected service list. Please retry.");
    }
    this.rows.clear();
    this.sections.replaceChildren();
    for (const [group, heading] of StatusDashboard.SECTIONS) {
      const services = data.services.filter((s) => s.group === group);
      if (services.length) this.sections.append(this.createSection(group, heading, services));
    }
    this.loaded = true;
  }

  /**
   * Create a section: a heading and a table of its services.
   * @param {string} group - "account" or "public".
   * @param {string} heading - The section's heading.
   * @param {Object[]} services - The services in it.
   * @returns {HTMLElement} The section.
   */
  createSection(group, heading, services) {
    const section = this.element("section", "mb-4");
    section.append(this.element("h2", "h5 mb-3", heading));
    if (group === "account") {
      section.append(
        this.element(
          "p",
          "small text-body-secondary",
          `Connection and saved access for ${this.username}.`,
        ),
      );
    }
    const table = this.element("table", "table align-middle status-table mb-0");
    const header = table.createTHead().insertRow();
    const columns = ["Status", "Service", ...(group === "account" ? ["Credentials"] : [])];
    for (const text of [...columns, "Details", "Duration", "Actions"]) {
      const th = this.element("th", text === "Details" ? "w-100" : "text-nowrap", text);
      th.scope = "col";
      if (["Duration", "Actions"].includes(text)) th.classList.add("text-end");
      header.append(th);
    }
    const body = table.createTBody();
    services.forEach((service) => body.append(this.createRow(service)));
    const responsive = this.element("div", "table-responsive");
    responsive.setAttribute("role", "region");
    responsive.setAttribute("aria-label", heading);
    responsive.tabIndex = 0;
    responsive.append(table);
    section.append(responsive);
    return section;
  }

  /**
   * Create a service's row, and remember its cells for later updates.
   * @param {Object} service - The service, as the API lists it.
   * @returns {HTMLTableRowElement} The row.
   */
  createRow(service) {
    const el = this.element("tr", "status-service");

    const identity = this.element("th", "status-identity fw-normal");
    identity.scope = "row";
    const name = this.element(service.url ? "a" : "span", "fw-semibold", service.display_name);
    if (service.url) {
      name.href = service.url;
      name.target = "_blank";
      name.rel = "noopener noreferrer";
      name.title = `Open ${service.url_label || service.display_name} in a new tab`;
      name.classList.add(
        "link-body-emphasis",
        "link-underline-opacity-0",
        "link-underline-opacity-100-hover",
      );
      name.append(
        this.icon("fa-arrow-up-right-from-square fa-xs ms-1 text-body-secondary"),
        this.element("span", "visually-hidden", " (opens in a new tab)"),
      );
    }
    identity.append(name);

    const connection = this.element("td", "text-nowrap");
    const badge = this.element("span", `badge ${StatusDashboard.STATUS.unknown[1]}`, "Waiting");
    connection.append(this.element("span", "visually-hidden", "Connection: "), badge);

    const access = this.element("td", "text-nowrap small");

    const details = this.element("td", "status-details text-break");
    const message = this.element("p", "small text-body-secondary mb-1", "Waiting for check…");
    const checked = this.element("small", "d-block text-body-secondary", "Not checked yet");
    details.append(message, checked);

    const duration = this.element(
      "td",
      "text-end text-nowrap font-monospace small text-body-secondary",
      "—",
    );

    const actions = this.element("td", "text-end text-nowrap");
    let manage = null;
    if (service.manage_url) {
      manage = this.element("a", "btn btn-outline-primary btn-sm me-1");
      manage.href = service.manage_url;
      this.setIcon(manage, "fa-pencil");
      manage.setAttribute("aria-label", `Manage ${service.display_name} credentials`);
      manage.title = `Manage ${service.display_name} credentials`;
      actions.append(manage);
    }
    const retry = this.element("button", "btn btn-outline-secondary btn-sm");
    retry.type = "button";
    this.setIcon(retry, "fa-rotate-right");
    retry.setAttribute("aria-label", `Check ${service.display_name} again`);
    retry.title = `Check ${service.display_name} again`;
    retry.addEventListener("click", () => this.fetchStatus(service.name, { refresh: true }));
    actions.append(retry);

    el.append(connection, identity);
    if (service.group === "account") el.append(access);
    el.append(details, duration, actions);
    this.rows.set(service.name, {
      service,
      el,
      badge,
      access,
      checked,
      retry,
      manage,
      details,
      message,
      duration,
      data: null,
      checking: false,
    });
    return el;
  }

  /**
   * Whether a status response has the shape the dashboard expects.
   * @param {Object} data - The parsed response.
   * @param {Object} service - The service it is for.
   * @returns {boolean} `true` if it can be rendered.
   */
  static isStatus(data, service) {
    return (
      !!data &&
      Object.hasOwn(StatusDashboard.STATUS, data.status) &&
      typeof data.message === "string" &&
      Number.isFinite(data.latency_ms) &&
      Number.isFinite(Date.parse(data.timestamp)) &&
      (service.group !== "account" || Object.hasOwn(StatusDashboard.ACCESS, data.credentials))
    );
  }

  /**
   * Check one service and render the result.
   * @param {string} name - The service's name.
   * @param {Object} [options]
   * @param {boolean} [options.refresh=false] - Skip the server's cached result.
   */
  async fetchStatus(name, { refresh = false } = {}) {
    const row = this.rows.get(name);
    if (!row || row.checking) return;
    row.checking = true;
    this.renderRow(row);
    this.renderSummary();
    try {
      const url = `/api${row.service.endpoint}${refresh ? "?refresh=1" : ""}`;
      const data = await this.requestJSON(url);
      if (!StatusDashboard.isStatus(data, row.service)) {
        throw new StatusError("GOATS returned an unexpected status. Please retry.");
      }
      row.data = data;
    } catch (error) {
      const offline = error instanceof TypeError;
      row.data = {
        status: "unknown",
        credentials: row.service.group === "account" ? "unchecked" : null,
        message: offline ? "Could not connect to GOATS. Please retry." : error.message,
        timestamp: null,
        latency_ms: null,
        errorCode: offline ? "network" : error.code || "error",
      };
    } finally {
      row.checking = false;
      this.renderRow(row);
      this.renderSummary();
    }
  }

  /**
   * Check every service, `CONCURRENCY` at a time, loading the list first if needed.
   * @param {Object} [options] - Passed on to `fetchStatus`.
   */
  async refreshAll(options = {}) {
    if (this.refreshing) return;
    this.refreshing = true;
    this.loadError = null;
    this.renderSummary();
    try {
      if (!this.loaded) await this.loadServices();
      const queue = [...this.rows.keys()];
      const worker = async () => {
        while (queue.length) await this.fetchStatus(queue.shift(), options);
      };
      const workers = Math.min(StatusDashboard.CONCURRENCY, queue.length);
      await Promise.all(Array.from({ length: workers }, worker));
    } catch (error) {
      this.loadError =
        error instanceof TypeError
          ? "Could not load services. Check the connection and retry."
          : error.message;
    } finally {
      this.refreshing = false;
      this.renderSummary();
    }
  }

  /**
   * Whether a row shows a problem. Optional credentials left unconfigured are not one.
   * @param {Object} row - The row.
   * @returns {boolean} `true` if the service is not available or refused its credentials.
   */
  needsAttention(row) {
    if (!row.data) return false;
    const rejected = row.service.group === "account" && row.data.credentials === "rejected";
    return row.data.status !== "ok" || rejected;
  }

  /**
   * Render a row from its last result and whether it is being checked.
   * @param {Object} row - The row.
   */
  renderRow(row) {
    const data = row.data;
    row.el.setAttribute("aria-busy", String(row.checking));
    if (row.retry.disabled !== row.checking) {
      row.retry.disabled = row.checking;
      this.setIcon(row.retry, "fa-rotate-right", row.checking);
    }
    if (!data) {
      row.badge.textContent = row.checking ? "Checking…" : "Waiting";
      return;
    }
    const [label, badgeClass] = StatusDashboard.STATUS[data.status];
    row.badge.textContent = label;
    row.badge.className = `badge ${badgeClass}`;
    row.el.classList.toggle("needs-attention", this.needsAttention(row));
    if (row.service.group === "account") {
      const [text, color, iconClass] = StatusDashboard.ACCESS[data.credentials];
      row.access.className = `text-nowrap small ${color}`.trim();
      row.access.replaceChildren(this.icon(`${iconClass} me-1`), text);
    }
    if (row.manage) {
      const missing = data.credentials === "missing";
      const label = `${missing ? "Add" : "Manage"} ${row.service.display_name} credentials`;
      row.manage.setAttribute("aria-label", label);
      row.manage.title = label;
    }
    row.checked.textContent = data.timestamp
      ? `Checked ${new Date(data.timestamp).toLocaleString()}`
      : "Last attempt failed";
    row.message.textContent = data.message;
    row.duration.textContent = Number.isFinite(data.latency_ms)
      ? `${Math.round(data.latency_ms)} ms`
      : "—";
    row.details.hidden = false;
  }

  /** Render the summary and the warning from every row's last result. */
  renderSummary() {
    const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
    const rows = [...this.rows.values()];
    const checking = rows.filter((row) => row.checking).length;
    const checked = rows.filter((row) => row.data);
    const down = checked.filter((row) => row.data.status === "down");
    const unknown = checked.filter((row) => row.data.status === "unknown");
    const rejected = checked.filter(
      (row) => row.service.group === "account" && row.data.credentials === "rejected",
    );
    const busy = this.refreshing || checking > 0;
    this.refresh.disabled = busy;
    const action = this.loaded ? "Refresh all" : "Retry";
    this.refresh.textContent = this.refreshing ? "Checking…" : action;
    // Screen readers wait for the checks to finish rather than read every step.
    this.summary.setAttribute("aria-busy", String(busy));

    const available = checked.length - down.length - unknown.length;
    const services = plural(rows.length, "service", "services");
    if (!this.loaded) {
      this.summary.textContent = this.loadError
        ? "Services could not be loaded"
        : "Loading services…";
    } else if (checked.length < rows.length) {
      this.summary.textContent = `Checking ${services}…`;
    } else if (available === rows.length) {
      const all = plural(rows.length, "service is", "services are");
      this.summary.textContent = `All ${all} available`;
    } else {
      this.summary.textContent = `${available} of ${services} available`;
    }

    this.renderNotice(this.noticeLines({ rows, checked, down, unknown, rejected }));
  }

  /**
   * Work out what the warning says. Each line is a list of text and lists of service names.
   * @param {Object} state - The rows, grouped by what their last check found.
   * @returns {Array<Array<string|string[]>>} The lines; none if nothing failed.
   */
  noticeLines({ rows, checked, down, unknown, rejected }) {
    const names = (failed) => failed.map((row) => row.service.display_name);
    const sessionFailure = checked.find((row) => row.data.errorCode === "session");
    if (this.loadError) return [[this.loadError]];
    if (sessionFailure) return [[sessionFailure.data.message]];
    if (rows.length && down.length === rows.length) {
      return [["GOATS could not reach any service. Check this server's connection and retry."]];
    }
    const lines = [];
    if (down.length) {
      const whose =
        down.length === 1
          ? "This is an outage of that service"
          : "These are outages of those services";
      lines.push(["Not available right now: ", names(down), `. ${whose}, not a GOATS fault.`]);
    }
    if (unknown.length) {
      lines.push(["Could not be checked: ", names(unknown), ". Retry the checks."]);
    }
    if (rejected.length) {
      lines.push([
        "Your stored credentials were rejected by: ",
        names(rejected),
        ". Update them with the edit button.",
      ]);
    }
    return lines;
  }

  /**
   * Render the warning, with service names in bold, or hide it if there is nothing to say.
   * @param {Array<Array<string|string[]>>} lines - What to say.
   */
  renderNotice(lines) {
    this.notice.hidden = lines.length === 0;
    this.notice.replaceChildren(
      ...lines.map((parts, index) => {
        const line = this.element("p", "mb-0");
        if (!index) line.append(this.icon("fa-triangle-exclamation me-2"));
        for (const part of parts) {
          if (typeof part === "string") {
            line.append(part);
            continue;
          }
          part.forEach((name, i) => {
            if (i) line.append(", ");
            line.append(this.element("strong", "", name));
          });
        }
        return line;
      }),
    );
  }
}
