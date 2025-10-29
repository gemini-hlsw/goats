/**
 * Class representing a dynamic UI for editing a source profile.
 */
class SourceProfileEditor {
  #container;
  #profileSelect;
  #sedSelect;
  #sedFormContainer;
  #sedRegistry = {};
  #readOnly;

  /**
   * Construct a source profile editor UI.
   * @param {HTMLElement} parentElement - The parent element to render into.
   * @param {Object} [options] - Optional configuration.
   * @param {Object} [options.data] - Preloaded profile/SED data.
   * @param {boolean} [options.readOnly=false] - Whether inputs are read-only.
   */
  constructor(parentElement, { data = {}, readOnly = false } = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("SourceProfileEditor expects an HTMLElement as the parent.");
    }

    this.#readOnly = readOnly;

    this.#container = Utils.createElement("div", "mb-3");
    const row = Utils.createElement("div", ["row", "g-3"]);

    const col1 = this.#createProfileSelect(data.profile);
    const col2 = this.#createSedSelect(data.sed);
    // Need to wrap this in a div to apply Bootstrap row/col classes properly.
    this.#sedFormContainer = Utils.createElement("div", ["row", "g-3"]);
    const wrapper = Utils.createElement("div", "col-12");
    wrapper.appendChild(this.#sedFormContainer);

    row.append(col1, col2, wrapper);
    this.#container.appendChild(row);
    parentElement.appendChild(this.#container);

    this.#registerSedRenderers();
    this.#setupEventListeners();
    if (data.sed) {
      // TODO: Fix SED name mapping here maybe.
      // FIXME: Remove debug log later after testing.
      this.#renderSedForm(data.sed, data);
    }
  }

  /**
   * Create the profile type <select> dropdown with hardcoded options.
   * @param {string} [selected="Point"] - Pre-selected value.
   * @returns {HTMLElement} Column container for the field.
   * @private
   */
  #createProfileSelect(selected = "point") {
    const col = Utils.createElement("div", "col-md-6");
    const label = Utils.createElement("label", "form-label");
    label.textContent = "Profile";
    const profileId = "sedProfileTypeSelect";
    label.htmlFor = profileId;

    const select = Utils.createElement("select", "form-select");
    select.name = profileId;
    select.id = profileId;
    select.disabled = this.#readOnly;

    // Hardcode options for now; will be dynamic later.
    const options = [
      { value: "point", label: "Point", disabled: false },
      { value: "gaussian", label: "Gaussian", disabled: true },
      { value: "uniform", label: "Uniform", disabled: true },
    ];

    for (const { value, label, disabled } of options) {
      const opt = Utils.createElement("option");
      opt.value = value;
      opt.textContent = label;
      if (disabled) opt.disabled = true;
      select.appendChild(opt);
    }

    select.value = selected;
    col.append(label, select);
    this.#profileSelect = select;
    return col;
  }

  /**
   * Create the SED <select> dropdown.
   * @param {string} [selected=""] - Pre-selected value.
   * @returns {HTMLElement} Column container for the field.
   * @private
   */
  #createSedSelect(selected = "") {
    const col = Utils.createElement("div", "col-md-6");
    const label = Utils.createElement("label", "form-label");
    label.textContent = "SED";
    const sedId = "sedTypeSelect";
    label.htmlFor = sedId;

    const select = Utils.createElement("select", "form-select");
    select.name = sedId;
    select.id = sedId;
    select.disabled = this.#readOnly;

    // Hardcode options for now; will be dynamic later.
    const options = [
      { value: "", label: "" },
      { value: "blackBodyTempK", label: "Black Body" },
      { value: "stellarLibrary", label: "Stellar Library", disabled: true },
      { value: "coolStar", label: "Cool Star", disabled: true },
      { value: "galaxy", label: "Galaxy", disabled: true },
      { value: "planet", label: "Planet", disabled: true },
      { value: "quasar", label: "Quasar", disabled: true },
      { value: "hiiRegion", label: "HII Region", disabled: true },
      { value: "planetaryNebula", label: "Planetary Nebula", disabled: true },
      { value: "powerLaw", label: "Power Law", disabled: true },
      { value: "fluxDensities", label: "Flux Densities", disabled: true },
      {
        value: "fluxDensitiesAttachment",
        label: "Flux Densities Attachment",
        disabled: true,
      },
    ];

    for (const { value, label, disabled } of options) {
      const opt = Utils.createElement("option");
      opt.value = value;
      opt.textContent = label;
      if (disabled) opt.disabled = true;
      select.appendChild(opt);
    }

    select.value = selected;
    col.append(label, select);
    this.#sedSelect = select;
    return col;
  }

  /**
   * Register renderers and extractors for each supported SED type.
   * @private
   */
  #registerSedRenderers() {
    this.#sedRegistry["blackBodyTempK"] = {
      render: (data = {}) => {
        const col = Utils.createElement("div", "col-md-6");

        const label = Utils.createElement("label", "form-label");
        label.textContent = "Temperature";
        const inputId = "sedBlackBodyTempK";
        label.htmlFor = inputId;

        const inputGroup = Utils.createElement("div", "input-group");
        const input = Utils.createElement("input", "form-control");
        input.type = "number";
        input.name = inputId;
        input.value = data.temperature ?? "10000";
        input.min = "0";
        input.id = inputId;
        if (this.#readOnly) input.disabled = true;

        const suffix = Utils.createElement("span", "input-group-text");
        suffix.textContent = "\u00B0K";

        inputGroup.append(input, suffix);
        col.append(label, inputGroup);
        return col;
      },
      extract: (formContainer) => {
        // FIXME: Don't need this anymore; can directly query the form data.
        return {};
      },
    };
  }

  /**
   * Setup event listeners for interactivity.
   * @private
   */
  #setupEventListeners() {
    this.#profileSelect.addEventListener("change", () => {
      // Profile-specific logic if needed later.
    });

    this.#sedSelect.addEventListener("change", (e) => {
      this.#renderSedForm(e.target.value);
    });
  }

  /**
   * Render the appropriate SED input form based on selected type.
   * @param {string} sedType - Type of SED to render.
   * @param {Object} [data={}] - Optional data to prefill fields.
   * @private
   */
  #renderSedForm(sedType, data = {}) {
    this.#sedFormContainer.innerHTML = "";
    const entry = this.#sedRegistry[sedType];
    if (entry?.render) {
      const form = entry.render(data);
      this.#sedFormContainer.appendChild(form);
    } else if (sedType) {
      const warning = Utils.createElement("div", ["alert", "alert-warning", "col-12"]);
      warning.textContent = `SED type "${sedType}" is not yet supported.`;
      this.#sedFormContainer.appendChild(warning);
      console.warn(`Unregistered SED type: "${sedType}"`);
    }
  }

  /**
   * Get the selected values from the UI.
   * @returns {Object|null} - Extracted values, or null if required fields are missing.
   */
  getValues() {
    const profile = this.#profileSelect.value;
    if (!profile) return null;

    const result = { profile };

    if (profile === "Point") {
      const sed = this.#sedSelect.value;
      if (!sed) return null;

      result.sed = sed;

      const entry = this.#sedRegistry[sed];
      if (entry?.extract) {
        Object.assign(result, entry.extract(this.#sedFormContainer));
      }
    }

    return result;
  }

  /**
   * Toggle read-only mode on all input elements.
   * @param {boolean} flag - Whether to enable read-only mode.
   */
  setReadOnly(flag) {
    this.#readOnly = flag;
    this.#profileSelect.disabled = flag;
    this.#sedSelect.disabled = flag;

    // Disable/enable input fields if rendered
    const inputs = this.#sedFormContainer.querySelectorAll("input");
    for (const input of inputs) {
      input.disabled = flag;
    }
  }
}
