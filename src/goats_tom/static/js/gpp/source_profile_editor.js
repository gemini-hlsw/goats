/**
 * Class representing a dynamic UI for editing a source profile.
 */
class SourceProfileEditor {
  #container;
  #profileCol;
  #profileSelect;
  #sedCol;
  #sedSelect;
  #sedFormContainer;
  #sedRegistry = {};

  /**
   * Construct a source profile editor UI.
   * @param {HTMLElement} parentElement - The parent element to render into.
   */
  constructor(parentElement) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("SourceProfileEditor expects an HTMLElement as the parent.");
    }

    this.#container = Utils.createElement("div", "mb-3");
    const row = Utils.createElement("div", ["row", "g-3"]);

    this.#profileCol = this.#createProfileSelect();
    this.#sedCol = this.#createSedSelect();
    // Holds the SED-specific input UI.
    this.#sedFormContainer = Utils.createElement("div", ["row", "g-3"]);
    // Need to wrap in a col to preserve spacing.
    const sedWrapperCol = Utils.createElement("div", "col-12");
    sedWrapperCol.appendChild(this.#sedFormContainer);

    row.append(this.#profileCol, this.#sedCol, sedWrapperCol);
    this.#container.appendChild(row);
    parentElement.appendChild(this.#container);

    this.#registerSedRenderers();
    this.#setupEventListeners();
  }

  /**
   * Create the profile type select field.
   * @returns {HTMLElement}
   * @private
   */
  #createProfileSelect() {
    const col = Utils.createElement("div", "col-md-6");
    const label = Utils.createElement("label", "form-label");
    label.textContent = "Profile";
    label.htmlFor = "profileType";

    const select = Utils.createElement("select", "form-select");
    select.name = "profileType";
    select.id = "profileType";

    const options = [
      { value: "Point", label: "Point", disabled: false },
      { value: "Gaussian", label: "Gaussian", disabled: true },
      { value: "Uniform", label: "Uniform", disabled: true },
    ];

    for (const { value, label, disabled } of options) {
      const opt = Utils.createElement("option");
      opt.value = value;
      opt.textContent = label;
      if (disabled) opt.disabled = true;
      select.appendChild(opt);
    }

    select.value = "Point";
    col.append(label, select);
    this.#profileSelect = select;
    return col;
  }

  /**
   * Create the SED selection dropdown.
   * @returns {HTMLElement}
   * @private
   */
  #createSedSelect() {
    const col = Utils.createElement("div", "col-md-6");
    const label = Utils.createElement("label", "form-label");
    label.textContent = "SED";
    label.htmlFor = "sedType";

    const select = Utils.createElement("select", "form-select");
    select.name = "sedType";
    select.id = "sedType";

    const options = [
      // Want 'empty' option like Explore.
      { value: "", label: "" },
      { value: "Black Body", label: "Black Body" },
      // TODO: Add new SED options here.
    ];

    for (const { value, label } of options) {
      const opt = Utils.createElement("option");
      opt.value = value;
      opt.textContent = label;
      select.appendChild(opt);
    }

    col.append(label, select);
    this.#sedSelect = select;
    return col;
  }

  /**
   * Register renderers and extractors for each supported SED type.
   * Each entry defines how to display its inputs and retrieve their values.
   * @private
   */
  #registerSedRenderers() {
    // Need a method to 'render' and a method to 'extract' the values.
    this.#sedRegistry["Black Body"] = {
      render: () => {
        const col = Utils.createElement("div", "col-md-6");

        const label = Utils.createElement("label", "form-label");
        label.textContent = "Temperature";
        label.htmlFor = "blackBodyTemperature";

        const inputGroup = Utils.createElement("div", "input-group");
        const input = Utils.createElement("input", "form-control");
        input.type = "number";
        input.name = "temperature";
        input.value = "10000";
        input.min = "0";
        input.id = "blackBodyTemperature";

        const suffix = Utils.createElement("span", "input-group-text");
        suffix.textContent = "\u00B0K";

        inputGroup.append(input, suffix);
        col.append(label, inputGroup);
        return col;
      },
      extract: (formContainer) => {
        const input = formContainer.querySelector("#blackBodyTemperature");
        const value = parseFloat(input?.value ?? "");
        return Number.isNaN(value) ? {} : { temperature: value };
      },
    };

    // Additional SEDs can be added as { render: () => HTMLElement, extract: (container:
    // HTMLElement) => object }.
  }

  /**
   * Setup event listeners for interactivity.
   * @private
   */
  #setupEventListeners() {
    this.#profileSelect.addEventListener("change", () => {
      // TODO: Handle future profile-specific behavior here.
    });

    this.#sedSelect.addEventListener("change", (e) => {
      const sed = e.target.value;
      this.#sedFormContainer.innerHTML = "";

      // Clear existing form and render SED-specific fields if available.
      const entry = this.#sedRegistry[sed];
      if (entry?.render) {
        const form = entry.render();
        this.#sedFormContainer.appendChild(form);
      }
    });
  }

  /**
   * Extract the selected source profile configuration, including SED-specific parameters.
   * @returns {{profile: string, sed?: string, [key: string]: any} | null}
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

    // TODO: Handle other profile types.
    return result;
  }
}
