/**
 * Class representing a dynamic UI for editing or displaying brightness entries.
 */
class BrightnessesEditor {
  #container;
  #table;
  #idCounter = 0;
  #readOnly = false;
  #addButton;
  #bands;
  #units;

  /**
   * Construct a brightnesses editor UI.
   *
   * @param {HTMLElement} parentElement - The parent element to render into.
   * @param {Object=} options - Optional configuration.
   * @param {Array<{band:string,value:string,units:string}>} [options.data] -
   *   Initial brightness payload. If omitted, starts empty (editable mode will add a blank row).
   * @param {string[]} [options.bands] - Optional default band choices if no data is given.
   * @param {string[]} [options.units] - Optional default unit choices if no data is given.
   * @param {boolean} [options.readOnly=false] - Whether the editor should start in readonly mode.
   */
  constructor(parentElement, options = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("BrightnessesEditor expects an HTMLElement as the parent.");
    }

    this.#readOnly = options.readOnly ?? false;

    // Default bands/units.
    // FIXME: This should come from gpp-client in the future.
    this.#bands = options.bands ?? [
      "SLOAN_U",
      "SLOAN_G",
      "SLOAN_R",
      "SLOAN_I",
      "SLOAN_Z",
      "U",
      "B",
      "V",
      "R",
      "I",
      "Y",
      "J",
      "H",
      "K",
      "L",
      "M",
      "N",
      "Q",
      "AP",
      "GAIA",
      "GAIA_BP",
      "GAIA_RP",
    ];
    this.#units = options.units ?? [
      "VEGA_MAGNITUDE",
      "AB_MAGNITUDE",
      "JANSKY",
      "W_PER_M_SQUARED_PER_UM",
      "ERG_PER_S_PER_CM_SQUARED_PER_A",
      "ERG_PER_S_PER_CM_SQUARED_PER_HZ",
    ];

    this.#container = Utils.createElement("div", "mb-3");
    this.#table = Utils.createElement("div", ["row", "g-3"]);
    this.#container.append(this.#table);

    // Add button (visible only in editable mode).
    this.#addButton = Utils.createElement("button", [
      "btn",
      "btn-outline-primary",
      "mt-3",
    ]);
    this.#addButton.type = "button";
    this.#addButton.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;
    this.#addButton.addEventListener("click", () => {
      this.#table.appendChild(this.#createInputGroup());
    });

    if (this.#readOnly) {
      this.#addButton.classList.add("d-none");
    }
    this.#container.append(this.#addButton);

    parentElement.appendChild(this.#container);

    // Load initial data (or start empty).
    this.load(options.data ?? []);
  }

  /**
   * Load brightness entries into the editor, wiping any previous rows.
   * @param {Array<{band:string,value:string,units:string}>} data - Brightness payload.
   */
  load(data) {
    this.#table.innerHTML = "";
    this.#idCounter = 0;

    if (!Array.isArray(data) || data.length === 0) {
      if (!this.#readOnly) {
        this.#table.appendChild(this.#createInputGroup());
      }
      // TODO: Show "No brightnesses defined" message in readonly mode?
      return;
    }

    for (const entry of data) {
      this.#table.appendChild(
        this.#createInputGroup(entry.band, entry.value, entry.units)
      );
    }
  }

  /**
   * Toggle readonly/editable mode without rebuilding rows.
   * @param {boolean} flag - True to set readonly, false to allow editing.
   */
  setReadOnly(flag) {
    this.#readOnly = flag;
    const rows = this.#table.querySelectorAll('[data-role="brightness-col"]');

    rows.forEach((col) => {
      const inputs = col.querySelectorAll("input, select, button");
      inputs.forEach((el) => {
        if (el.tagName === "BUTTON") {
          el.classList.toggle("d-none", flag);
        } else {
          el.disabled = flag;
        }
      });
    });

    if (this.#addButton) {
      this.#addButton.classList.toggle("d-none", flag);
    }
  }

  /**
   * Create and return a new input group row.
   * @private
   * @param {string} band - Band name.
   * @param {string|number} value - Brightness value.
   * @param {string} units - Units.
   * @returns {HTMLElement} - The created row element.
   */
  #createInputGroup(band = "", value = "", units = "") {
    const col = Utils.createElement("div", "col-12");
    col.dataset.role = "brightness-col";

    const inputGroup = Utils.createElement("div", "input-group");
    const uniqueId = `brightness-${this.#idCounter++}`;

    const bandSelect = this.#createSelect(
      `${uniqueId}-band`,
      "brightnessBand",
      this.#bands,
      band
    );

    const valueInput = Utils.createElement("input", "form-control");
    valueInput.type = "number";
    valueInput.step = "any";
    valueInput.name = "brightnessValue";
    valueInput.id = `${uniqueId}-value`;
    valueInput.value = value;

    const unitSelect = this.#createSelect(
      `${uniqueId}-units`,
      "brightnessUnits",
      this.#units,
      units
    );

    const removeBtn = Utils.createElement("button", ["btn", "btn-danger"]);
    removeBtn.type = "button";
    removeBtn.innerHTML = `<i class="fa-solid fa-minus"></i>`;
    removeBtn.title = "Remove";
    removeBtn.addEventListener("click", () => col.remove());

    if (this.#readOnly) {
      removeBtn.classList.add("d-none");
      bandSelect.disabled = true;
      valueInput.disabled = true;
      unitSelect.disabled = true;
    }

    inputGroup.append(bandSelect, valueInput, unitSelect, removeBtn);
    col.appendChild(inputGroup);
    return col;
  }

  /**
   * Create a <select> element with options.
   *
   * @private
   * @param {string} id - Element ID.
   * @param {string} name - Name attribute.
   * @param {string[]} options - Option values.
   * @param {string} selectedValue - Value to select by default.
   * @returns {HTMLSelectElement}
   */
  #createSelect(id, name, options, selectedValue = "") {
    const select = Utils.createElement("select", "form-select");
    select.name = name;
    select.id = id;

    options.forEach((opt) => {
      const optionEl = Utils.createElement("option");
      optionEl.value = opt;
      optionEl.textContent = opt;
      if (opt === selectedValue) {
        optionEl.selected = true;
      }
      select.appendChild(optionEl);
    });

    return select;
  }

  /**
   * Get current values from the editor, skipping rows with no value.
   *
   * @returns {Array<{band:string,units:string,value:number}>}
   */
  getValues() {
    const cols = this.#table.querySelectorAll('[data-role="brightness-col"]');
    return Array.from(cols)
      .map((col) => {
        const band = col.querySelector('select[name="brightnessBand"]')?.value ?? "";
        const units = col.querySelector('select[name="brightnessUnits"]')?.value ?? "";
        const valueStr =
          col.querySelector('input[name="brightnessValue"]')?.value ?? "";
        const value = parseFloat(valueStr);
        return { band, units, value };
      })
      .filter(({ value }) => !Number.isNaN(value));
  }
}
