const { JSDOM } = require("jsdom");
const fs = require("fs");
const path = require("path");
const { js_dir } = require("./testConfig.js");
// The dashboard builds its elements with `Utils`, which the page loads first.
const script = ["utils.js", "status_dashboard.js"]
  .map((file) => fs.readFileSync(path.join(js_dir, file), "utf8"))
  .join("\n");
const SERVICES = [
  { name: "goa", display_name: "GOA", group: "account", endpoint: "/status/goa/", url: "https://archive.gemini.edu", manage_url: "/users/1/goa/" },
  { name: "antares", display_name: "ANTARES", group: "public", endpoint: "/status/antares/", url: "https://antares.noirlab.edu" },
];
const status = (extra = {}) => ({ status: "ok", credentials: "verified", message: "Available", latency_ms: 12, timestamp: "2026-09-30T10:00:00Z", ...extra });
const response = (data, code = 200) => ({ ok: code === 200, status: code, json: async () => data });
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const windows = [];
afterEach(() => windows.splice(0).forEach((window) => window.close()));
function build(handler, timeout = 35000) {
  const dom = new JSDOM('<div id="c"></div>', { runScripts: "outside-only" });
  const { window } = dom;
  windows.push(window);
  window.fetch = jest.fn(handler || (async (url) => response(url === "/api/status/" ? { services: SERVICES } : status())));
  window.eval(script + "; window.Dashboard = StatusDashboard;");
  window.Dashboard.REQUEST_TIMEOUT_MS = timeout;
  const dashboard = new window.Dashboard(window.document.getElementById("c"), { username: "owner" });
  return { window, dashboard, container: window.document.getElementById("c") };
}

test("shows accessible actions, separate account state and actual check time", async () => {
  const { dashboard, container } = build();
  await dashboard.ready;
  expect(container.querySelectorAll("h2").length).toBe(2);
  expect(container.textContent).toContain("Verified");
  const manage = container.querySelector('a[href="/users/1/goa/"]');
  expect(manage.querySelector("i.fa-pencil")).not.toBeNull();
  expect(manage.getAttribute("aria-label")).toBe("Manage GOA credentials");
  expect(container.querySelector('[aria-label="Check GOA again"] i.fa-rotate-right')).not.toBeNull();
  expect(container.querySelector('[aria-label="Check GOA again"]')).not.toBeNull();
  expect(dashboard.rows.get("goa").checked.textContent).toContain("Checked");
  expect(dashboard.notice.hidden).toBe(true);
  expect(dashboard.refresh.disabled).toBe(false);
});

test("a failure shows one warning, never an error, and highlights the row", async () => {
  const { dashboard, container } = build(async (url) => response(url === "/api/status/"
    ? { services: SERVICES } : status(url.includes("antares") ? { status: "down", credentials: null } : {})));
  await dashboard.ready;
  expect(container.querySelectorAll(".alert").length).toBe(1);
  expect(dashboard.notice.hidden).toBe(false);
  expect(dashboard.notice.classList.contains("alert-warning")).toBe(true);
  expect(container.querySelector(".alert-danger, .bg-danger-subtle, .text-danger")).toBeNull();
  expect(dashboard.rows.get("goa").el.classList.contains("needs-attention")).toBe(false);
  expect(dashboard.rows.get("antares").el.classList.contains("needs-attention")).toBe(true);
  // Nobody here can fix an external service: there is nothing to filter by.
  expect(container.querySelector('input[type="checkbox"]')).toBeNull();
});

test("optional unconfigured accounts offer to add them without an outage warning", async () => {
  const { dashboard } = build(async (url) => response(url === "/api/status/" ? { services: SERVICES } : status({ credentials: "missing" })));
  await dashboard.ready;
  const manage = dashboard.rows.get("goa").manage;
  // Always the pencil: only the tooltip says the credentials are missing.
  expect(manage.querySelector("i.fa-pencil")).not.toBeNull();
  expect(manage.querySelector("i.fa-plus")).toBeNull();
  expect(manage.title).toBe("Add GOA credentials");
  // Optional credentials are not a problem: no warning, and a plain row.
  expect(dashboard.notice.hidden).toBe(true);
  expect(dashboard.rows.get("goa").el.classList.contains("needs-attention")).toBe(false);
  expect(dashboard.rows.get("goa").access.textContent).toBe("Not configured");
});

test.each([null, { detail: "error" }, { services: [] }])("invalid service list is recoverable: %p", async (data) => {
  const { dashboard, window } = build(async () => response(data));
  await dashboard.ready;
  expect(dashboard.notice.hidden).toBe(false);
  expect(dashboard.refresh.disabled).toBe(false);
  window.fetch.mockImplementation(async (url) => response(url === "/api/status/" ? { services: SERVICES } : status()));
  await dashboard.refreshAll({ refresh: true });
  expect(dashboard.rows.size).toBe(2);
  expect(dashboard.notice.hidden).toBe(true);
});

test("expired session is explained instead of leaving a blank panel", async () => {
  const { dashboard } = build(async () => response({ detail: "denied" }, 403));
  await dashboard.ready;
  expect(dashboard.notice.textContent).toContain("Sign in again");
  expect(dashboard.refresh.disabled).toBe(false);
});

test("network failure during initial load retries the service list", async () => {
  const { dashboard, window } = build(async () => { throw new TypeError("network"); });
  await dashboard.ready;
  expect(dashboard.loaded).toBe(false);
  window.fetch.mockImplementation(async (url) => response(url === "/api/status/" ? { services: SERVICES } : status()));
  await dashboard.refreshAll();
  expect(window.fetch.mock.calls.filter(([url]) => url === "/api/status/")).toHaveLength(2);
  expect(dashboard.rows.size).toBe(2);
});

test("malformed status cannot leave refresh disabled", async () => {
  const { dashboard } = build(async (url) => response(url === "/api/status/" ? { services: SERVICES } : null));
  await dashboard.ready;
  expect(dashboard.rows.get("goa").data.status).toBe("unknown");
  expect(dashboard.refresh.disabled).toBe(false);
  expect(dashboard.rows.get("goa").retry.disabled).toBe(false);
});

test("timeout aborts the request and restores controls", async () => {
  let signal;
  const { dashboard } = build(async (url, options) => {
    if (url === "/api/status/") return response({ services: SERVICES });
    signal = options.signal;
    return new Promise(() => {});
  }, 10);
  await dashboard.ready;
  expect(signal.aborted).toBe(true);
  expect(dashboard.rows.get("goa").data.message).toContain("timed out");
  expect(dashboard.refresh.disabled).toBe(false);
  expect(dashboard.notice.textContent).toBe("Could not be checked: GOA, ANTARES. Retry the checks.");
});

test("preserves last result while rechecking and skips cached checks explicitly", async () => {
  const { dashboard, window } = build();
  await dashboard.ready;
  let resolve;
  window.fetch.mockImplementation(() => new Promise((done) => { resolve = done; }));
  const pending = dashboard.fetchStatus("goa", { refresh: true });
  expect(dashboard.rows.get("goa").badge.textContent).toBe("Available");
  expect(dashboard.rows.get("goa").retry.disabled).toBe(true);
  expect(window.fetch.mock.calls.at(-1)[0]).toContain("?refresh=1");
  resolve(response(status({ status: "down" })));
  await pending;
  expect(dashboard.rows.get("goa").badge.textContent).toBe("Not available");
});

test("limits concurrent requests to six", async () => {
  let active = 0, maximum = 0;
  const services = Array.from({ length: 9 }, (_, i) => ({ ...SERVICES[1], name: `s${i}`, endpoint: `/status/s${i}/` }));
  const { dashboard } = build(async (url) => {
    if (url === "/api/status/") return response({ services });
    active++; maximum = Math.max(maximum, active);
    await flush(); active--;
    return response(status());
  });
  await dashboard.ready;
  expect(maximum).toBe(6);
});

const withStatuses = (byName) => async (url) => response(url === "/api/status/"
  ? { services: SERVICES } : status(byName[url.split("/")[3]] || {}));

test("an outage is named as the external service's, not a GOATS fault", async () => {
  const { dashboard } = build(withStatuses({ antares: { status: "down", credentials: null } }));
  await dashboard.ready;
  expect(dashboard.notice.hidden).toBe(false);
  expect(dashboard.notice.textContent).toBe(
    "Not available right now: ANTARES. This is an outage of that service, not a GOATS fault."
  );
});

test("rejected credentials are named apart from outages", async () => {
  const { dashboard } = build(withStatuses({ goa: { credentials: "rejected" } }));
  await dashboard.ready;
  expect(dashboard.notice.textContent).toContain("rejected by: GOA");
  expect(dashboard.notice.textContent).not.toContain("outage");
});

test("the summary says what happens, and the warning skips optional credentials", async () => {
  const { dashboard } = build(withStatuses({
    goa: { credentials: "missing" },
    antares: { status: "down", credentials: null },
  }));
  await dashboard.ready;
  expect(dashboard.summary.textContent).toBe("1 of 2 services available");
  expect(dashboard.notice.querySelector("i.fa-triangle-exclamation")).not.toBeNull();
  expect(dashboard.notice.textContent).not.toContain("credential");
  expect(dashboard.notice.textContent).not.toContain("attention");
});

test("credential states carry their own colour", async () => {
  const { dashboard } = build(withStatuses({ goa: { credentials: "rejected" } }));
  await dashboard.ready;
  const access = dashboard.rows.get("goa").access;
  expect(access.textContent).toBe("Rejected");
  expect(access.classList.contains("text-warning-emphasis")).toBe(true);
  expect(access.querySelector("i.fa-circle-xmark")).not.toBeNull();
});

test("service names show they open a new tab", async () => {
  const { dashboard, container } = build();
  await dashboard.ready;
  const link = container.querySelector('a[href="https://archive.gemini.edu"]');
  expect(link.querySelector("i.fa-arrow-up-right-from-square")).not.toBeNull();
  expect(link.textContent).toBe("GOA (opens in a new tab)");
});

test("an expired session is recognised by its code, not its wording", async () => {
  const { dashboard, window } = build(async (url) => url === "/api/status/"
    ? response({ services: SERVICES }) : response({ detail: "denied" }, 403));
  await dashboard.ready;
  expect(dashboard.rows.get("goa").data.errorCode).toBe("session");
  expect(dashboard.notice.textContent).toContain("Sign in again");
});

test("healthy services use subtle badges, not solid colour", async () => {
  const { dashboard } = build();
  await dashboard.ready;
  const badge = dashboard.rows.get("goa").badge;
  expect(badge.textContent).toBe("Available");
  expect(badge.classList.contains("bg-success-subtle")).toBe(true);
  expect(badge.classList.contains("text-bg-success")).toBe(false);
});

test("the retry icon spins while a service is being checked", async () => {
  const { dashboard, window } = build();
  await dashboard.ready;
  window.fetch.mockImplementation(() => new Promise(() => {}));
  dashboard.fetchStatus("goa", { refresh: true });
  expect(dashboard.rows.get("goa").retry.querySelector("i.fa-spin")).not.toBeNull();
});

test("a healthy page says so once, without repeating the count", async () => {
  const { dashboard } = build();
  await dashboard.ready;
  expect(dashboard.summary.textContent).toBe("All 2 services are available");
  expect(dashboard.notice.hidden).toBe(true);
});

test("services that fail are named in bold in the warning", async () => {
  const { dashboard } = build(withStatuses({ antares: { status: "down", credentials: null } }));
  await dashboard.ready;
  const bold = [...dashboard.notice.querySelectorAll("strong")].map((el) => el.textContent);
  expect(bold).toEqual(["ANTARES"]);
});

test("credential issues alone do not make the services look unavailable", async () => {
  const { dashboard } = build(withStatuses({ goa: { credentials: "missing" } }));
  await dashboard.ready;
  expect(dashboard.summary.textContent).toBe("All 2 services are available");
  expect(dashboard.notice.hidden).toBe(true);
});

test("services that could not be checked are not reported as down", async () => {
  const { dashboard } = build(withStatuses({ antares: { status: "unknown", credentials: null } }));
  await dashboard.ready;
  expect(dashboard.summary.textContent).toBe("1 of 2 services available");
  expect(dashboard.notice.textContent).toBe("Could not be checked: ANTARES. Retry the checks.");
});

test("a login redirect is explained as an expired session", async () => {
  const { dashboard } = build(async (url) => url === "/api/status/"
    ? response({ services: SERVICES })
    : { ok: true, status: 200, redirected: true, json: async () => { throw new SyntaxError("html"); } });
  await dashboard.ready;
  expect(dashboard.rows.get("goa").data.errorCode).toBe("session");
  expect(dashboard.notice.textContent).toContain("Sign in again");
});

test("only the summary is a live region, and it waits for the checks", async () => {
  const { dashboard, container } = build();
  expect(dashboard.summary.getAttribute("aria-busy")).toBe("true");
  await dashboard.ready;
  expect(container.querySelectorAll('[role="status"]')).toHaveLength(1);
  expect(dashboard.summary.getAttribute("role")).toBe("status");
  expect(dashboard.summary.getAttribute("aria-busy")).toBe("false");
});

test("the layout uses Bootstrap utilities, not a page stylesheet", async () => {
  const { dashboard, container } = build();
  await dashboard.ready;
  expect(dashboard.bar.classList.contains("d-flex")).toBe(true);
  expect(container.querySelector("table").classList.contains("table-borderless")).toBe(false);
  const link = container.querySelector('a[href="https://archive.gemini.edu"]');
  expect(link.classList.contains("link-underline-opacity-0")).toBe(true);
});
