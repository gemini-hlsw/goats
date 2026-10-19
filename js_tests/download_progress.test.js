const { JSDOM } = require("jsdom");
const fs = require("fs");
const path = require("path");
const { js_dir } = require("./testConfig.js");

const script = fs.readFileSync(path.join(js_dir, "download_progress.js"), "utf8");
const windows = [];
afterEach(() => windows.splice(0).forEach((window) => window.close()));

function build() {
  const dom = new JSDOM(
    `<span id="downloadBadge" class="d-none">0</span>
     <div id="downloadTasksBanner"></div>
     <div id="noDownloadsMessage"></div>`,
    { runScripts: "outside-only" }
  );
  windows.push(dom.window);
  dom.window.eval(script + "\n;window.update = updateDownloadProgress;");
  const byId = (id) => dom.window.document.getElementById(id);
  return {
    window: dom.window,
    badge: byId("downloadBadge"),
    list: byId("downloadTasksBanner"),
    empty: byId("noDownloadsMessage"),
  };
}

const progress = (id, extra = {}) => ({
  unique_id: id, label: `Download ${id}`, message: "", status: "Running",
  downloaded_bytes: "1 KB", done: false, error: false, ...extra,
});

test("the badge counts running downloads and hides when they finish", () => {
  const { window, badge } = build();

  window.update(progress("a"));
  window.update(progress("b"));
  window.update(progress("a"));
  expect(badge.textContent).toBe("2");
  expect(badge.classList.contains("d-none")).toBe(false);

  window.update(progress("a", { done: true }));
  expect(badge.textContent).toBe("1");

  window.update(progress("b", { error: true }));
  expect(badge.classList.contains("d-none")).toBe(true);
});

test("the badge caps at 9+ like the bell", () => {
  const { window, badge } = build();

  for (let i = 0; i < 12; i++) window.update(progress(`d${i}`));

  expect(badge.textContent).toBe("9+");
});

test("a download is shown as a row with its label, size and status", () => {
  const { window, list } = build();

  window.update(progress("a"));

  const row = list.querySelector(".download-row");
  expect(row.querySelector(".download-title").textContent).toBe("Download a");
  expect(row.querySelector(".download-meta").textContent).toContain("1 KB");
  expect(row.querySelector(".download-meta").textContent).toContain("Running");
});

test("the empty message hides while there are rows and returns after them", () => {
  const { window, list, empty } = build();
  // Finished rows are removed after a delay; run it straight away.
  window.setTimeout = (callback) => callback();

  window.update(progress("a"));
  expect(empty.classList.contains("d-none")).toBe(true);

  window.update(progress("a", { done: true, status: "Done" }));
  expect(list.childElementCount).toBe(0);
  expect(empty.classList.contains("d-none")).toBe(false);
});
