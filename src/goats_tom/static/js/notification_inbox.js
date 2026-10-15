/**
 * Drives the navbar notification panel: live "inbox" WebSocket updates, the
 * Unread/All tabs.
 */
class NotificationInbox {
  /** How many notifications the panel keeps, matching the server-side render. */
  static MAX_ITEMS = 10;

  /** Counts above this show as "9+", matching the server-side render. */
  static MAX_COUNT = 9;

  static MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /**
   * Compact age of a timestamp. Mirrors the `short_time` template filter.
   * @param {Date} when
   * @param {Date} [now]
   * @returns {string} "now", "5m", "3h", "2d" or a date like "8 Oct".
   */
  static shortTime(when, now = new Date()) {
    const minutes = Math.floor((now - when) / 60000);
    if (minutes < 1) return "now";
    if (minutes < 60) return `${minutes}m`;
    if (minutes < 60 * 24) return `${Math.floor(minutes / 60)}h`;
    if (minutes < 60 * 24 * 7) return `${Math.floor(minutes / (60 * 24))}d`;
    // Same month abbreviations as Django's "M" format, so both renders agree.
    const month = NotificationInbox.MONTHS[when.getMonth()];
    const date = `${when.getDate()} ${month}`;
    return when.getFullYear() === now.getFullYear() ? date : `${date} ${when.getFullYear()}`;
  }

  /**
   * @param {HTMLElement} panel - The dropdown panel (`#notificationPanel`).
   * @param {Object} elements - Elements outside the panel.
   * @param {HTMLElement} elements.badge - Unread count on the bell.
   * @param {HTMLElement} [elements.icon] - Bell icon, swung when a notification arrives.
   * @param {Function} [onNew] - Called with each new notification, e.g. to show a toast.
   */
  constructor(panel, { badge, icon = null }, onNew = () => {}) {
    this.panel = panel;
    this.badge = badge;
    this.icon = icon;
    this.onNew = onNew;
    this.list = panel.querySelector("#notificationList");
    this.empty = panel.querySelector("#notificationEmpty");
    this.tabCount = panel.querySelector("#notificationTabCount");
    this.unread = Number.parseInt(badge.textContent, 10) || 0;

    panel.addEventListener("click", (event) => {
      const tab = event.target.closest("[data-inbox-filter]");
      if (tab) this.setFilter(tab.dataset.inboxFilter);
    });
    this.sync();
  }

  /**
   * Apply one "inbox" update from the server.
   * @param {Object} data - The WebSocket payload.
   * @param {number} data.unread - Unread count after the change.
   * @param {Object|null} data.notification - The new notification, if any.
   * @param {number[]} [data.read_ids] - Notifications just read or resolved.
   */
  update(data) {
    this.setUnread(data.unread);
    this.markRead(data.unread ? data.read_ids || [] : null);
    if (data.notification) {
      this.prepend(data.notification);
      this.ring();
      this.onNew(data.notification);
    }
  }

  /**
   * Show the unread count on the bell and the Unread tab.
   * @param {number} count
   */
  setUnread(count) {
    this.unread = Math.max(0, count);
    const text =
      this.unread > NotificationInbox.MAX_COUNT
        ? `${NotificationInbox.MAX_COUNT}+`
        : String(this.unread);
    for (const element of [this.badge, this.tabCount]) {
      if (!element) continue;
      element.textContent = text;
      element.classList.toggle("d-none", !this.unread);
    }
    this.sync();
  }

  /**
   * Show only unread notifications, or all of them.
   * @param {"unread"|"all"} filter
   */
  setFilter(filter) {
    this.list.dataset.filter = filter;
    for (const tab of this.panel.querySelectorAll("[data-inbox-filter]")) {
      const active = tab.dataset.inboxFilter === filter;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
    }
    this.sync();
  }

  /**
   * Stop treating notifications as unread.
   * @param {number[]|null} ids - Notifications now read, or `null` for all.
   */
  markRead(ids) {
    const read = ids && new Set(ids.map(String));
    for (const row of this.#rows()) {
      if (!read || read.has(row.dataset.notificationId)) row.classList.remove("unread");
    }
    this.sync();
  }

  /** Show the empty state for the current tab. */
  sync() {
    const rows = this.#rows();
    const unreadOnly = this.list.dataset.filter === "unread";
    const visible = rows.filter((row) => !unreadOnly || row.classList.contains("unread"));
    this.empty.classList.toggle("d-none", visible.length > 0);
    const title = this.empty.querySelector("[data-empty-title]");
    if (title) title.textContent = unreadOnly ? "You're all caught up" : "No notifications";
  }

  /** Refresh every relative time shown in the panel. */
  refreshTimes(now = new Date()) {
    for (const time of this.list.querySelectorAll("time[datetime]")) {
      time.textContent = NotificationInbox.shortTime(new Date(time.dateTime), now);
    }
  }

  /** Swing the bell once; restarting it if a swing is already running. */
  ring() {
    if (!this.icon) return;
    this.icon.classList.remove("ringing");
    void this.icon.offsetWidth;
    this.icon.classList.add("ringing");
    this.icon.addEventListener("animationend", () => this.icon.classList.remove("ringing"), {
      once: true,
    });
  }

  /**
   * Add a new, unread notification to the top of the panel.
   * @param {Object} notification - Serialized notification.
   */
  prepend(notification) {
    const id = encodeURIComponent(notification.id);
    const row = this.#element("div", "notification-row unread");
    row.dataset.notificationId = String(notification.id);

    const kind = this.#element("span", `notification-kind kind-${notification.color || "secondary"}`);
    kind.setAttribute("aria-hidden", "true");
    kind.append(this.#element("i", `fa-solid ${notification.icon || "fa-bell"}`));

    const title = this.#element("a", "notification-title stretched-link", notification.title);
    title.href = `/notifications/${id}/`;
    const time = this.#element("time", "notification-time", "now");
    time.dateTime = notification.created_at || new Date().toISOString();
    const top = this.#element("div", "notification-top");
    top.append(title, time);
    const body = this.#element("div", "notification-body");
    body.append(top, this.#element("p", "notification-message", notification.message));

    const dot = this.#element("span", "notification-dot");
    dot.append(this.#element("span", "visually-hidden", "Unread"));

    row.append(kind, body, dot);
    this.list.prepend(row);
    while (this.list.children.length > NotificationInbox.MAX_ITEMS) {
      this.list.lastElementChild.remove();
    }
    this.sync();
  }

  #rows() {
    return [...this.list.querySelectorAll(".notification-row")];
  }

  #element(tag, className, text) {
    const element = document.createElement(tag);
    element.className = className;
    if (text !== undefined) element.textContent = String(text ?? "");
    return element;
  }
}
