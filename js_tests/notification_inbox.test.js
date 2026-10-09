const { JSDOM } = require("jsdom");
const fs = require("fs");
const path = require("path");
const { js_dir } = require("./testConfig.js");

const script = fs.readFileSync(path.join(js_dir, "notification_inbox.js"), "utf8");
const windows = [];
afterEach(() => windows.splice(0).forEach((window) => window.close()));

const row = (id, { unread = false } = {}) => `
  <div class="notification-row ${unread ? "unread" : ""}" data-notification-id="${id}">
    <a class="notification-title" href="/notifications/${id}/">Title ${id}</a>
    <time datetime="2026-10-09T10:00:00Z">old</time>
  </div>`;

function build(rows = "", unread = 0) {
  const dom = new JSDOM(
    `<span id="icon"></span><span id="badge" class="${unread ? "" : "d-none"}">${unread}</span>
     <div id="notificationPanel">
       <button data-inbox-filter="unread" class="active"></button>
       <button data-inbox-filter="all"></button>
       <span id="notificationTabCount"></span>
       <div id="notificationList" data-filter="unread">${rows}</div>
       <div id="notificationEmpty"><strong data-empty-title></strong></div>
     </div>`,
    { runScripts: "outside-only" }
  );
  const { window } = dom;
  windows.push(window);
  window.eval(script + "\n;window.Inbox = NotificationInbox;");
  const doc = window.document;
  const onNew = jest.fn();
  const inbox = new window.Inbox(
    doc.getElementById("notificationPanel"),
    { badge: doc.getElementById("badge"), icon: doc.getElementById("icon") },
    onNew
  );
  return { window, doc, inbox, onNew };
}

const notification = (id) => ({
  id, title: `Title ${id}`, message: `Message ${id}`, color: "warning",
  icon: "fa-user-clock", autohide: false, created_at: "2026-10-09T10:00:00Z",
});
const ids = (doc) => [...doc.querySelectorAll(".notification-row")].map((r) => r.dataset.notificationId);
const click = (window, element) => element.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));

test("a new notification is prepended with its icon, swings the bell and calls back", () => {
  const { doc, inbox, onNew } = build();

  inbox.update({ unread: 1, notification: notification(4) });

  const item = doc.querySelector(".notification-row");
  expect(item.classList.contains("unread")).toBe(true);
  expect(item.querySelector(".notification-kind").className).toContain("kind-warning");
  expect(item.querySelector(".notification-kind i").className).toContain("fa-user-clock");
  expect(item.querySelector("a").getAttribute("href")).toBe("/notifications/4/");
  expect(item.querySelector("time").textContent).toBe("now");
  expect(doc.getElementById("badge").textContent).toBe("1");
  expect(doc.getElementById("notificationTabCount").textContent).toBe("1");
  expect(doc.getElementById("icon").classList.contains("ringing")).toBe(true);
  expect(doc.getElementById("notificationEmpty").classList.contains("d-none")).toBe(true);
  expect(onNew).toHaveBeenCalledWith(notification(4));
});

test("the panel keeps only the latest ten", () => {
  const { doc, inbox } = build();

  for (let id = 1; id <= 12; id++) inbox.update({ unread: id, notification: notification(id) });

  expect(ids(doc)).toHaveLength(10);
  expect(ids(doc)[0]).toBe("12");
});

test("text is never interpreted as HTML", () => {
  const { doc, inbox } = build();

  inbox.update({ unread: 1, notification: { id: 1, title: "<img src=x onerror=alert(1)>", message: "<b>hi</b>" } });

  expect(doc.querySelector("#notificationList img")).toBeNull();
  expect(doc.querySelector("#notificationList b")).toBeNull();
});

test("counts above nine show as 9+ on the bell and the tab", () => {
  const { doc, inbox } = build();

  inbox.setUnread(12);

  expect(doc.getElementById("badge").textContent).toBe("9+");
  expect(doc.getElementById("notificationTabCount").textContent).toBe("9+");
});

test("the Unread tab shows the caught-up state when nothing is unread", () => {
  const { window, doc } = build(row(1));
  const empty = doc.getElementById("notificationEmpty");

  expect(empty.classList.contains("d-none")).toBe(false);
  expect(empty.textContent).toContain("You're all caught up");

  click(window, doc.querySelector('[data-inbox-filter="all"]'));

  expect(doc.getElementById("notificationList").dataset.filter).toBe("all");
  expect(doc.querySelector('[data-inbox-filter="all"]').getAttribute("aria-selected")).toBe("true");
  expect(empty.classList.contains("d-none")).toBe(true);
});

test("other tabs follow reads", () => {
  const { doc, inbox } = build(row(1, { unread: true }) + row(2, { unread: true }), 2);

  inbox.update({ unread: 1, notification: null, read_ids: [2] });

  expect(ids(doc)).toEqual(["1", "2"]);
  expect(doc.querySelector('[data-notification-id="1"]').classList.contains("unread")).toBe(true);
  expect(doc.querySelector('[data-notification-id="2"]').classList.contains("unread")).toBe(false);
});

test("nothing stays unread once the count reaches zero", () => {
  const { doc, inbox } = build(row(1, { unread: true }) + row(2, { unread: true }), 2);

  inbox.update({ unread: 0, notification: null, read_ids: [] });

  expect(doc.querySelectorAll(".notification-row.unread")).toHaveLength(0);
});

test("shortTime mirrors the server filter", () => {
  const { window } = build();
  const now = new Date("2026-10-09T12:00:00Z");
  const ago = (ms) => new Date(now - ms);
  const short = (when) => window.Inbox.shortTime(when, now);

  expect(short(ago(20 * 1000))).toBe("now");
  expect(short(ago(5 * 60000))).toBe("5m");
  expect(short(ago(3 * 3600000))).toBe("3h");
  expect(short(ago(2 * 86400000))).toBe("2d");
  expect(short(new Date("2026-09-08T12:00:00Z"))).toBe("8 Sep");
  expect(short(new Date("2025-09-08T12:00:00Z"))).toBe("8 Sep 2025");
});

test("refreshTimes updates every relative time", () => {
  const { doc, inbox } = build(row(1));

  inbox.refreshTimes(new Date("2026-10-09T10:05:00Z"));

  expect(doc.querySelector("time").textContent).toBe("5m");
});
