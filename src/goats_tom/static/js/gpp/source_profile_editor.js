/**
 * Class representing the editor for source profile configuration.
 */
class SourceProfileEditor {
  /** @type {HTMLElement} @private */
  #container;
  /** @type {HTMLSelectElement} @private */
  #profileSelect;
  /** @type {HTMLSelectElement} @private */
  #sedSelect;
  /** @type {HTMLElement} @private */
  #sedFormContainer;
  /** @type {SEDRegistry} @private */
  #sedRegistry;
  /** @type {ProfileRegistry} @private */
  #profileRegistry;
  /** @type {boolean} @private */
  #debug;
  /** @type {string} @private */
  #debugTag = "[SourceProfileEditor]";

  /**
   * Create a new SourceProfileEditor instance.
   * @param {HTMLElement} parentElement - The container to attach this editor to.
   * @param {Object} [options]
   * @param {Object} [options.data={}] - Initial source profile data.
   * @param {boolean} [options.debug=false] - Enable debug logging.
   */
  constructor(parentElement, { data = {}, debug = false } = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("SourceProfileEditor expects an HTMLElement as the parent.");
    }
    this.#debug = debug;

    this.#profileRegistry = new ProfileRegistry();
    this.#sedRegistry = new SEDRegistry();

    // Parse input profile and SED keys.
    const profileKey = Object.keys(data)[0] ?? "point";
    const profileData = data[profileKey] ?? {};
    const bandNormalized = profileData.bandNormalized ?? {};
    const sedData = bandNormalized.sed ?? {};
    const sedKey = Object.keys(sedData).find((key) => sedData[key] != null) ?? "";

    // Determine if the input is unsupported.
    const hasProfile = this.#profileRegistry.isSupported(profileKey);
    const hasSed = this.#sedRegistry.isSupported(sedKey);
    const notSupported = !hasProfile || !hasSed;

    this.#logDebug(`Detected profile: ${profileKey}`);
    this.#logDebug(`Detected SED: ${sedKey}`);

    // Build container and append early so it's available even if unsupported.
    this.#container = Utils.createElement("div", "mb-3");
    parentElement.appendChild(this.#container);

    if (notSupported) {
      this.#renderUnsupportedWarning(data);
      return;
    }

    // Build form layout.
    const row = Utils.createElement("div", ["row", "g-3"]);
    const col1 = this.#createProfileSelect(profileKey);
    const col2 = this.#createSedSelect(sedKey);

    this.#sedFormContainer = Utils.createElement("div", ["row", "g-3"]);
    const wrapper = Utils.createElement("div", "col-12");
    wrapper.appendChild(this.#sedFormContainer);

    row.append(col1, col2, wrapper);
    this.#container.appendChild(row);

    if (sedKey) {
      this.#renderSedForm(sedKey, sedData[sedKey]);
    }

    this.#setupEventListeners();
  }

  /**
   * Enable or disable debug logging at runtime.
   * @param {boolean} flag
   */
  setDebug(flag) {
    this.#debug = flag;
    this.#logDebug(`Setting debug to ${flag}`);
  }

  /**
   * Logs a debug message if debugging is enabled.
   *
   * @param {string} message - The message to log.
   * @private
   */
  #logDebug(message) {
    if (this.#debug) console.debug(`${this.#debugTag} ${message}`);
  }

  /**
   * Create the profile select dropdown.
   * @param {string} selected - The selected profile type.
   * @returns {HTMLElement}
   * @private
   */
  #createProfileSelect(selected = "point") {
    this.#logDebug(`Creating profile select. Selected: ${selected}`);
    const col = Utils.createElement("div", "col-md-6");
    const label = Utils.createElement("label", "form-label");
    label.textContent = "Profile";
    const profileId = "sedProfileTypeSelect";
    label.htmlFor = profileId;

    const select = Utils.createElement("select", "form-select");
    select.name = profileId;
    select.id = profileId;

    const options = this.#profileRegistry.getOptions();
    for (const { value, label } of options) {
      const opt = Utils.createElement("option");
      opt.value = value;
      opt.textContent = label;
      select.appendChild(opt);
    }

    select.value = selected;
    this.#profileSelect = select;
    col.append(label, select);
    return col;
  }

  /**
   * Create the SED select dropdown.
   * @param {string} selected - The selected SED type.
   * @returns {HTMLElement}
   * @private
   */
  #createSedSelect(selected = "") {
    this.#logDebug(`Creating SED select. Selected: ${selected}`);
    const col = Utils.createElement("div", "col-md-6");
    const label = Utils.createElement("label", "form-label");
    label.textContent = "SED";
    const sedId = "sedTypeSelect";
    label.htmlFor = sedId;

    const select = Utils.createElement("select", "form-select");
    select.name = sedId;
    select.id = sedId;

    for (const { value, label } of this.#sedRegistry.getOptions()) {
      const opt = Utils.createElement("option");
      opt.value = value;
      opt.textContent = label;
      select.appendChild(opt);
    }

    select.value = selected;
    this.#sedSelect = select;
    col.append(label, select);
    return col;
  }

  /**
   * Set up change listeners for dropdowns.
   * @private
   */
  #setupEventListeners() {
    this.#logDebug("Setting up event listeners.");
    if (!this.#profileSelect || !this.#sedSelect) return;
    this.#profileSelect.addEventListener("change", () => {
      this.#logDebug(`Profile changed to: ${this.#profileSelect.value}`);
    });

    this.#sedSelect.addEventListener("change", (e) => {
      const sedType = e.target.value;
      this.#logDebug(`SED changed to: ${sedType}`);
      this.#renderSedForm(sedType);
    });
  }

  /**
   * Render the selected SED form.
   * @param {string} sedType - The selected SED type.
   * @param {Object} [data={}] - SED data to populate the form with.
   * @private
   */
  #renderSedForm(sedType, data = {}) {
    this.#logDebug(`Rendering SED form for: ${sedType}`);
    this.#sedFormContainer.innerHTML = "";

    const form = this.#sedRegistry.render(sedType, data);
    if (form) {
      this.#sedFormContainer.appendChild(form);
    } else {
      this.#logDebug("No form rendered (blank or unsupported SED).");
    }
  }

  /**
   * Render a warning for unsupported input.
   * @param {Object} data - Raw source profile data.
   * @private
   */
  #renderUnsupportedWarning(data) {
    this.#logDebug(`Unsupported input. Showing warning.`);
    const id = "notSupportedSourceProfile";
    const accordionId = `${id}Accordion`;
    const collapseId = `${id}Collapse`;
    const alert = Utils.createElement("div", ["alert", "alert-warning", "mt-2"]);
    alert.innerHTML = `
      <div class="alert-heading">
        <h6>Unsupported Source Profile</h6>
      </div>
      This configuration is not currently supported by the editor. The data has been preserved below for reference, but it will not be editable.
      <div class="accordion accordion-flush mt-3" id="${accordionId}">
        <div class="accordion-item">
          <h2 class="accordion-header">
            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse"
              data-bs-target="#${collapseId}" aria-expanded="false" aria-controls="${collapseId}">
              View raw source profile data
            </button>
          </h2>
          <div id="${collapseId}" class="accordion-collapse collapse" data-bs-parent="#${accordionId}">
            <div class="accordion-body accordion-body-sm-overflow">
              <pre><code>${JSON.stringify(data, null, 2)}</code></pre>
            </div>
          </div>
        </div>
      </div>
    `;
    this.#container.append(alert);
  }
}
/**
 * A registry for Spectral Energy Distribution (SED) types.
 *
 * Each SED type must define:
 * - a `label` (string) shown in the UI,
 * - a `render(data: object): HTMLElement` function that returns the UI elements for editing.
 *
 * To register a new SED type, use:
 *
 * ```js
 * sedRegistry.register("newType", {
 *   label: "My SED Type",
 *   render: (data) => { ... }
 * });
 * ```
 */
class SEDRegistry {
  /** @type {Record<string, {label: string, render: (data: object) => HTMLElement}>} @private */
  #registry = {};

  constructor() {
    // Register default SED type to render nothing aka reset.
    this.register("", {
      label: "",
      render: () => null,
    });
    this.register("blackBodyTempK", {
      label: "Black Body",
      render: this.#renderBlackBodyTempK,
    });
  }

  /**
   * Register a new SED type.
   * @param {string} key - Internal SED key (e.g., "blackBodyTempK").
   * @param {{ label: string, render: (data: object) => HTMLElement }} definition
   */
  register(key, definition) {
    this.#registry[key] = definition;
  }

  /**
   * Return the list of selectable SED options.
   * @returns {Array<{value: string, label: string}>}
   */
  getOptions() {
    return Object.entries(this.#registry).map(([value, { label }]) => ({
      value,
      label,
    }));
  }

  /**
   * Check if a given SED type is supported.
   * @param {string} sedType
   * @returns {boolean}
   */
  isSupported(sedType) {
    return sedType in this.#registry;
  }

  /**
   * Render the form UI for a given SED type, or return null if unsupported.
   * @param {string} sedType
   * @param {object} [data={}]
   * @returns {HTMLElement|null}
   */
  render(sedType, data = {}) {
    return this.isSupported(sedType) ? this.#registry[sedType].render(data) : null;
  }

  /**
   * Default renderer for Black Body temperature input.
   * @private
   * @param {object} data
   * @returns {HTMLElement}
   */
  #renderBlackBodyTempK(data = {}) {
    const col = Utils.createElement("div", "col-md-6");
    const label = Utils.createElement("label", "form-label");
    label.textContent = "Temperature";
    const inputId = "sedBlackBodyTempK";
    label.htmlFor = inputId;

    const inputGroup = Utils.createElement("div", "input-group");
    const input = Utils.createElement("input", "form-control");
    input.type = "number";
    input.name = inputId;
    input.id = inputId;
    input.min = "0";
    input.value = data.temperature ?? "10000";

    const suffix = Utils.createElement("span", "input-group-text");
    suffix.textContent = "\u00B0K";

    inputGroup.append(input, suffix);
    col.append(label, inputGroup);
    return col;
  }
}

/**
 * Registry for supported source profile types.
 */
class ProfileRegistry {
  /** @type {Object<string, {label: string}>} @private */
  #registry;
  constructor() {
    this.#registry = {
      point: { label: "Point" },
    };
  }

  /**
   * Get supported profile options.
   * @returns {Array<{value: string, label: string}>}
   */
  getOptions() {
    return Object.entries(this.#registry).map(([value, { label }]) => ({
      value,
      label,
    }));
  }

  /**
   * Check if a profile is supported.
   * @param {string} profile
   * @returns {boolean}
   */
  isSupported(profile) {
    return profile in this.#registry;
  }
}
