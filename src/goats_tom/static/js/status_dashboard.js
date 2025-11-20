/**
 * StatusDashboard
 *
 * A dashboard widget that renders a service status table, fetches health checks from
 * the backend, and provides retry and "refresh all" functionality.
 */
class StatusDashboard {
  /** @type {HTMLElement} @private */
  #parent;

  /** @type {HTMLElement} @private */
  #container;

  /** @type {boolean} @private */
  #debug;

  /** @type {string} @private */
  #logTag = "[StatusDashboard]";

  /**
   * Stores all service row references indexed by service name.
   *
   * @type {Map<string, {light: HTMLElement, msg: HTMLElement, endpoint: string}>}
   * @private
   */
  #serviceRows = new Map();

  /**
   * Map of status to CSS class for the status light.
   *
   * @type {{ok: string, warning: string, down: string}}
   * @readonly
   */
  static STATUS_CLASSES = {
    ok: "text-success",
    warning: "text-warning",
    down: "text-danger",
  };

  /** @type {HTMLElement} @private */
  #alert;

  /** @type {HTMLElement} @private */
  #tbody;

  /**
   * Construct a new StatusDashboard instance.
   *
   * @param {HTMLElement} parentElement - Element to attach the dashboard into.
   * @param {{debug?: boolean}} [options] - Optional configuration flags.
   */
  constructor(parentElement, { debug = false } = {}) {
    this.#parent = parentElement;
    this.#debug = debug;

    this.#container = this.#create();
    this.#parent.appendChild(this.#container);

    this.#loadServices();
  }

  /**
   * Create the full DOM layout for the dashboard, including:
   *   - error banner
   *   - table + header + tbody
   *   - refresh-all button
   *
   * @returns {HTMLElement} The dashboard container element.
   * @private
   */
  #create() {
    const wrapper = document.createElement("div");

    // Create table.
    const table = document.createElement("table");
    table.classList.add("table", "table-borderless", "align-middle");
    const headerRow = table.createTHead().insertRow();
    // Create table headers.
    ["", "Service", "", ""].forEach((text) => {
      const th = document.createElement("th");
      th.textContent = text;
      headerRow.appendChild(th);
    });

    // Create table body.
    this.#tbody = document.createElement("tbody");
    table.appendChild(this.#tbody);
    wrapper.appendChild(table);

    // Create alert.
    this.#alert = document.createElement("div");
    this.#alert.classList.add("alert", "alert-danger", "d-none");
    this.#alert.role = "alert";
    wrapper.appendChild(this.#alert);

    // Create refresh all button.
    const refreshAllBtn = document.createElement("button");
    refreshAllBtn.className = "btn btn-primary mt-2";
    refreshAllBtn.textContent = "Refresh All";
    refreshAllBtn.onclick = () => this.refreshAll();
    wrapper.appendChild(refreshAllBtn);
    return wrapper;
  }

  /**
   * Display an error banner with the given message.
   *
   * @param {string} message - Error text to show.
   * @private
   */
  #showErrorAlert(message) {
    this.#alert.textContent = message;
    this.#alert.classList.remove("d-none");
  }

  /**
   * Hide the error banner.
   *
   * @private
   */
  #hideErrorAlert() {
    this.#alert.classList.add("d-none");
    this.#alert.textContent = "";
  }

  /**
   * Create a fully populated <tr> element for a service and store references for later
   * status updates.
   *
   * @param {{name: string, display_name: string, endpoint: string}} service
   * @returns {HTMLTableRowElement}
   * @private
   */
  #createRow(service) {
    const tr = document.createElement("tr");

    // Add status light.
    const light = document.createElement("span");

    const lightCell = tr.insertCell();
    lightCell.classList.add("text-end", "align-middle");
    lightCell.appendChild(light);

    // Insert service name in cell.
    tr.insertCell().textContent = service.display_name;

    // Insert message cell.
    const msg = tr.insertCell();
    // Set minimum width for message cell.
    msg.style.minWidth = "12rem";

    this.#setLoadingState(light, msg);

    // Add retry button.
    const retryBtn = document.createElement("button");
    retryBtn.className = "btn btn-sm btn-secondary";
    retryBtn.textContent = "Retry";
    retryBtn.onclick = () => this.fetchStatus(service.name);

    const retryCell = tr.insertCell();
    retryCell.className = "text-end";
    retryCell.appendChild(retryBtn);

    // Store references to the row elements.
    this.#serviceRows.set(service.name, {
      light,
      msg,
      endpoint: service.endpoint,
    });

    this.#logDebug(`Created row for ${service.name}`);

    return tr;
  }

  /**
   * Load the initial list of services from the backend, then build rows and fetch each
   * service's status.
   *
   * @returns {Promise<void>}
   * @private
   */
  async #loadServices() {
    let data;
    try {
      // Fetch the list of services from the API.
      const response = await fetch("/api/status/");
      // Parse the JSON response.
      data = await response.json();
    } catch (err) {
      this.#logError("Failed to fetch service list:", err);
      this.#showErrorAlert("Error loading services. Please try refreshing the page.");
      return;
    }

    this.#hideErrorAlert();

    // Add a row for each service.
    // Use a document fragment for better performance.
    const fragment = document.createDocumentFragment();

    for (const service of data.services) {
      const row = this.#createRow(service);
      fragment.appendChild(row);
    }

    this.#tbody.appendChild(fragment);

    // Fetch the status for each service.
    await Promise.all(data.services.map((s) => this.fetchStatus(s.name)));
  }

  /**
   * Fetch the live status for a single service and update the UI.
   *
   * @param {string} name - The service identifier.
   * @returns {Promise<void>}
   */
  async fetchStatus(name) {
    // Get the row elements for the service.
    const row = this.#serviceRows.get(name);
    if (!row) return;

    const { light, msg, endpoint } = row;

    // Reset to loading.
    this.#setLoadingState(light, msg);

    try {
      const response = await fetch(`/api${endpoint}`);
      const data = await response.json();

      msg.textContent = data.message;
      this.#applyStatusLight(light, data.status);
    } catch (err) {
      this.#logError(`Failed to fetch status for ${name}:`, err);
      msg.textContent = "Failed to fetch.";
      this.#applyStatusLight(light, "down");
    }
  }

  /**
   * Apply the loading state to the light + message cell.
   *
   * @param {HTMLElement} light
   * @param {HTMLElement} msgElement
   * @private
   */
  #setLoadingState(light, msgElement) {
    light.className = "status-light text-muted status-loading";
    msgElement.textContent = "Loading...";
  }

  /**
   * Refresh every service simultaneously.
   *
   * @returns {Promise<void>}
   */
  async refreshAll() {
    // Refresh the status of all services.
    await Promise.all(
      Array.from(this.#serviceRows.keys()).map((name) => this.fetchStatus(name))
    );
  }

  /**
   * Apply the correct class for a given status value.
   *
   * @param {HTMLElement} light
   * @param {string} status - One of "ok" | "warning" | "down".
   * @private
   */
  #applyStatusLight(light, status) {
    // Remove existing status classes.
    light.classList.remove(
      "status-loading",
      "text-muted",
      "text-success",
      "text-warning",
      "text-danger"
    );

    const colorClass = StatusDashboard.STATUS_CLASSES[status] || "text-muted";

    light.classList.add("status-light", colorClass);
  }

  /**
   * Debug logger.
   *
   * @param {string} msg
   * @private
   */
  #logDebug(msg) {
    if (this.#debug) console.debug(`${this.#logTag} ${msg}`);
  }

  /**
   * Error logger.
   *
   * @param {string} msg
   * @param {unknown} err
   * @private
   */
  #logError(msg, err) {
    console.error(this.#logTag, msg, err);
  }
}
