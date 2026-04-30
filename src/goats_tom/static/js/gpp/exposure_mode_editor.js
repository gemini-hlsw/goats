/**
 * Class representing an Exposure Mode editor.
 * - For IMAGING mode: handles multiple filters with tabs, each with its own exposure mode.
 * - For LONG_SLIT mode: handles a single exposure mode without filters.
 */
class ExposureModeEditor {
  #container;
  #readOnly;
  #idPrefix;
  #mode; // "imaging" or "longSlit"
  #exposures; // Array of {filter, select, inputs} for imaging, or single object for longSlit

  /**
   * Create an ExposureModeEditor.
   * @param {HTMLElement} parentElement - The parent container element.
   * @param {Object} options - Editor options.
   * @param {string} [options.mode="imaging"] - "imaging" or "longSlit".
   * @param {Array|Object} [options.data=null] - Initial data (array for imaging, object for longSlit).
   * @param {boolean} [options.readOnly=false] - Whether the fields should be read-only.
   * @param {string} [options.idPrefix="exposure"] - ID prefix for elements.
   */
  constructor(
    parentElement,
    { mode = "imaging", data = null, readOnly = false, idPrefix = "exposure" } = {}
  ) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error(
        "ExposureModeEditor expects an HTMLElement as the parent."
      );
    }

    this.#readOnly = readOnly;
    this.#idPrefix = idPrefix;
    this.#mode = mode.toLowerCase();
    this.#container = Utils.createElement("div", ["d-flex", "flex-column"]);
    parentElement.appendChild(this.#container);

    if (this.#mode === "imaging") {
      this.#exposures = this.#parseImagingData(data);
    } else {
      this.#exposures = this.#parseLongSlitData(data);
    }

    this.#render();
  }

  /**
   * Parse imaging data (array of {filter, exposureTimeMode}).
   * @private
   * @param {Array} data
   * @returns {Array}
   */
  #parseImagingData(data) {
    if (!Array.isArray(data)) return [];

    return data.map((item) => {
      const filter = item.filter ?? "";
      const exposureTimeMode = item.exposureTimeMode ?? {};
      const mode = exposureTimeMode?.signalToNoise != null
        ? "Signal / Noise"
        : "Time & Count";

      return {
        filter,
        exposureTimeMode,
        mode,
        select: null,
        inputs: {},
      };
    });
  }

  /**
   * Parse long-slit data (single {exposureTimeMode} object).
   * @private
   * @param {Object} data
   * @returns {Object}
   */
  #parseLongSlitData(data) {
    if (!data || typeof data !== "object") {
      data = { exposureTimeMode: {} };
    }

    // Detectar si data es directamente exposureTimeMode o si está anidado
    let exposureTimeMode;
    
    if (data.exposureTimeMode !== undefined) {
      // Estructura: { exposureTimeMode: { signalToNoise, timeAndCount } }
      exposureTimeMode = data.exposureTimeMode;
    } else if (data.signalToNoise !== undefined || data.timeAndCount !== undefined) {
      // Estructura directa: { signalToNoise, timeAndCount }
      exposureTimeMode = data;
    } else {
      // Estructura desconocida, asumir vacío
      exposureTimeMode = {};
    }

    const mode = exposureTimeMode?.signalToNoise != null
      ? "Signal / Noise"
      : "Time & Count";

    return {
      exposureTimeMode,
      mode,
      select: null,
      inputs: {},
    };
  }

  /**
   * Render the editor based on mode.
   * @private
   */
  #render() {
    this.#container.innerHTML = "";

    if (this.#mode === "imaging") {
      this.#renderImaging();
    } else {
      this.#renderLongSlit();
    }
  }

  /**
   * Render IMAGING mode with filter selector.
   * @private
   */
  #renderImaging() {
    if (this.#exposures.length === 0) return;

    // Filter selector
    const filterRow = Utils.createElement("div", ["row", "g-3", "mb-3"]);
    const filterCol = Utils.createElement("div", "col-md-6");
    const filterLabel = this.#createLabel("Select Filter", "filter-selector");
    
    const filterSelect = Utils.createElement("select", "form-select");
    filterSelect.id = "filter-selector";
    filterSelect.name = "filter-selector";
    
    this.#exposures.forEach((exposure, index) => {
      const opt = Utils.createElement("option");
      opt.value = index;
      opt.textContent = exposure.filter || `Filter ${index + 1}`;
      filterSelect.append(opt);
    });
    
    // Deshabilitar solo si readOnly AND no es imaging mode
    filterSelect.disabled = this.#readOnly && this.#mode !== "imaging";
    filterSelect.addEventListener("change", (e) => {
      this.#displayExposure(parseInt(e.target.value));
    });
    
    filterCol.append(filterLabel, filterSelect);
    filterRow.append(filterCol);
    this.#container.append(filterRow);

    // Content container for current exposure
    const contentContainer = Utils.createElement("div");
    contentContainer.id = "exposure-content";
    this.#container.append(contentContainer);

    // Display first exposure
    this.#displayExposure(0);
  }

  /**
   * Display a specific exposure's fields.
   * @private
   * @param {number} index
   */
  #displayExposure(index) {
    const contentContainer = this.#container.querySelector("#exposure-content");
    contentContainer.innerHTML = "";

    const exposure = this.#exposures[index];
    if (!exposure) return;

    // Mode selector
    exposure.select = this.#createSelect(
      `${this.#idPrefix}-select-${index}`,
      exposure.mode,
      () => this.#updateVisibility(index)
    );
    const selectCol = Utils.createElement("div", "col-12");
    selectCol.append(
      this.#createLabel("Exposure Mode", `${this.#idPrefix}-select-${index}`),
      exposure.select
    );
    const selectRow = Utils.createElement("div", ["row", "g-3", "mb-3"]);
    selectRow.append(selectCol);
    contentContainer.append(selectRow);

    // Input fields
    exposure.inputs = this.#buildInputs(
      `${this.#idPrefix}-${index}`,
      exposure.exposureTimeMode
    );
    this.#populateInputs(exposure.inputs, exposure.mode);
    contentContainer.append(this.#buildFieldsRow(exposure.inputs, exposure.mode));
  }

  /**
   * Render LONG_SLIT mode (single exposure mode).
   * @private
   */
  #renderLongSlit() {
    const exposure = this.#exposures;

    // Mode selector
    exposure.select = this.#createSelect(
      `${this.#idPrefix}-select`,
      exposure.mode,
      () => this.#updateVisibility()
    );
    const selectCol = Utils.createElement("div", "col-12");
    selectCol.append(
      this.#createLabel("Exposure Mode", `${this.#idPrefix}-select`),
      exposure.select
    );
    const selectRow = Utils.createElement("div", ["row", "g-3", "mb-3"]);
    selectRow.append(selectCol);
    this.#container.append(selectRow);

    // Input fields
    exposure.inputs = this.#buildInputs(
      this.#idPrefix,
      exposure.exposureTimeMode
    );
    this.#populateInputs(exposure.inputs, exposure.mode);
    this.#container.append(this.#buildFieldsRow(exposure.inputs, exposure.mode));
  }

  /**
   * Create the mode dropdown select.
   * @private
   * @param {string} id
   * @param {string} value
   * @param {Function} onChange
   * @returns {HTMLSelectElement}
   */
  #createSelect(id, value, onChange) {
    const select = Utils.createElement("select", "form-select");
    select.id = id;
    select.name = id;
    ["Signal / Noise", "Time & Count"].forEach((opt) => {
      const o = Utils.createElement("option");
      o.value = opt;
      o.textContent = opt;
      if (opt === value) o.selected = true;
      select.append(o);
    });
    select.disabled = this.#readOnly;
    select.addEventListener("change", onChange);
    return select;
  }

  /**
   * Build input elements for a single exposure.
   * @private
   * @param {string} idPrefix
   * @param {Object} exposureTimeMode
   * @returns {Object}
   */
  #buildInputs(idPrefix, exposureTimeMode) {
    const inputs = {};

    // Extraer valores de Signal / Noise
    const snValue = exposureTimeMode?.signalToNoise?.value ?? "";
    const snWavelength = exposureTimeMode?.signalToNoise?.at?.nanometers ?? "";

    // Extraer valores de Time & Count
    const timeSeconds = exposureTimeMode?.timeAndCount?.time?.seconds ?? "";
    const count = exposureTimeMode?.timeAndCount?.count ?? "";
    const tcWavelength = exposureTimeMode?.timeAndCount?.at?.nanometers ?? "";

    // Signal / Noise inputs
    inputs.snInput = this.#createNumberInput(
      "Signal / Noise",
      `${idPrefix}-sn`,
      snValue
    );
    inputs.snWavelengthInput = this.#createNumberInput(
      "λ for S/N",
      `${idPrefix}-sn-wl`,
      snWavelength,
      "nm"
    );

    // Time & Count inputs
    inputs.timeInput = this.#createNumberInput(
      "Exposure Time",
      `${idPrefix}-time`,
      timeSeconds,
      "s"
    );
    inputs.countInput = this.#createNumberInput(
      "Number of Exposures",
      `${idPrefix}-count`,
      count,
      "#"
    );
    inputs.tcWavelengthInput = this.#createNumberInput(
      "λ for S/N",
      `${idPrefix}-tc-wl`,
      tcWavelength,
      "nm"
    );

    return inputs;
  }

  /**
   * Populate inputs into a wrapper row and toggle visibility.
   * @private
   * @param {Object} inputs
   * @param {string} mode
   * @returns {HTMLElement}
   */
  #buildFieldsRow(inputs, mode) {
    const row = Utils.createElement("div", ["row", "g-3"]);
    const isSN = mode === "Signal / Noise";

    row.append(inputs.snInput);
    row.append(inputs.snWavelengthInput);
    row.append(inputs.timeInput);
    row.append(inputs.countInput);
    row.append(inputs.tcWavelengthInput);

    // Toggle visibility
    this.#toggleField(inputs.snInput, isSN);
    this.#toggleField(inputs.snWavelengthInput, isSN);
    this.#toggleField(inputs.timeInput, !isSN);
    this.#toggleField(inputs.countInput, !isSN);
    this.#toggleField(inputs.tcWavelengthInput, !isSN);

    return row;
  }

  /**
   * Populate input values from exposure data.
   * @private
   * @param {Object} inputs
   * @param {string} mode
   */
  #populateInputs(inputs, mode) {
    // Values are already set in #createNumberInput
  }

  /**
   * Create a labeled number input group.
   * @param {string} label - Label text.
   * @param {string} id - Input ID.
   * @param {string|number} value - Initial value.
   * @param {string} [suffix=""] - Optional suffix text.
   * @returns {HTMLDivElement}
   * @private
   */
  #createNumberInput(label, id, value, suffix = "") {
    const col = Utils.createElement("div", "col-md-6");
    const labelEl = this.#createLabel(label, id);
    const input = Utils.createElement("input", "form-control");
    input.id = id;
    input.name = id;
    input.type = "number";
    input.value = value;
    if (this.#readOnly) input.disabled = true;

    const group = suffix ? this.#wrapWithInputGroup(input, suffix) : input;
    col.append(labelEl, group);
    return col;
  }

  /**
   * Wrap an input in an input group with suffix.
   * @param {HTMLInputElement} input - Input element.
   * @param {string} suffixText - Suffix to display.
   * @returns {HTMLDivElement}
   * @private
   */
  #wrapWithInputGroup(input, suffixText) {
    const group = Utils.createElement("div", "input-group");
    const suffix = Utils.createElement("span", "input-group-text");
    suffix.textContent = suffixText;
    group.append(input, suffix);
    return group;
  }

  /**
   * Create a label element.
   * @param {string} text - Label content.
   * @param {string} htmlFor - Input ID.
   * @returns {HTMLLabelElement}
   * @private
   */
  #createLabel(text, htmlFor) {
    const label = Utils.createElement("label", "form-label");
    label.textContent = text;
    label.htmlFor = htmlFor;
    return label;
  }

  /**
   * Toggle a column's display using Bootstrap `d-none`.
   * @param {HTMLElement} col - Column element.
   * @param {boolean} show - Whether to show or hide it.
   * @private
   */
  #toggleField(col, show) {
    col.classList.toggle("d-none", !show);
  }

  /**
   * Update field visibility based on selected mode.
   * @private
   * @param {number} [index] - For imaging mode, the tab index. Omit for longSlit.
   */
  #updateVisibility(index) {
    const exposure = index !== undefined ? this.#exposures[index] : this.#exposures;
    const mode = exposure.select.value;
    const isSN = mode === "Signal / Noise";
    const inputs = exposure.inputs;

    this.#toggleField(inputs.snInput, isSN);
    this.#toggleField(inputs.snWavelengthInput, isSN);
    this.#toggleField(inputs.timeInput, !isSN);
    this.#toggleField(inputs.countInput, !isSN);
    this.#toggleField(inputs.tcWavelengthInput, !isSN);
  }

  /**
   * Get current values from the editor.
   * @returns {Array|Object}
   */
  getValues() {
    if (this.#mode === "imaging") {
      return this.#exposures.map((exposure) => ({
        filter: exposure.filter,
        exposureTimeMode: this.#getExposureTimeMode(exposure),
      }));
    } else {
      return {
        exposureTimeMode: this.#getExposureTimeMode(this.#exposures),
      };
    }
  }

  /**
   * Extract exposureTimeMode from exposure inputs.
   * @private
   * @param {Object} exposure
   * @returns {Object}
   */
  #getExposureTimeMode(exposure) {
    const mode = exposure.select.value;
    const inputs = exposure.inputs;

    if (mode === "Signal / Noise") {
      const sn = parseFloat(inputs.snInput.querySelector("input").value);
      const wavelength = parseFloat(
        inputs.snWavelengthInput.querySelector("input").value
      );
      return {
        signalToNoise: isNaN(sn)
          ? null
          : { value: sn, at: isNaN(wavelength) ? null : { nanometers: wavelength } },
        timeAndCount: null,
      };
    }

    const time = parseFloat(inputs.timeInput.querySelector("input").value);
    const count = parseInt(inputs.countInput.querySelector("input").value);
    const wavelength = parseFloat(
      inputs.tcWavelengthInput.querySelector("input").value
    );
    return {
      signalToNoise: null,
      timeAndCount: {
        time: isNaN(time) ? null : { seconds: time },
        count: isNaN(count) ? null : count,
        at: isNaN(wavelength) ? null : { nanometers: wavelength },
      },
    };
  }

  /**
   * Enable or disable all inputs.
   * @param {boolean} flag
   */
  setReadOnly(flag) {
    this.#readOnly = flag;
    const selects = this.#container.querySelectorAll("select");
    const inputs = this.#container.querySelectorAll("input");
    selects.forEach((s) => (s.disabled = flag));
    inputs.forEach((i) => (i.disabled = flag));
  }
}
