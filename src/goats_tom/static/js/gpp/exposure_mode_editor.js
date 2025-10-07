/**
 * Class representing an Exposure Mode editor (Signal / Noise or Time & Count).
 *
 * This is basically a copy of ElevationRangeEditor with different fields.
 */
class ExposureModeEditor {
  #container;
  #select;
  #readOnly;

  #snInput;
  #snWavelengthInput;
  #timeInput;
  #countInput;
  #tcWavelengthInput;

  /**
   * Create an ExposureModeEditor.
   * @param {HTMLElement} parentElement - The parent container element.
   * @param {Object} options - Editor options.
   * @param {Object} [options.data={}] - Initial exposure mode data.
   * @param {boolean} [options.readOnly=false] - Whether the fields should be read-only.
   */
  constructor(parentElement, { data = {}, readOnly = false } = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("ExposureModeEditor expects an HTMLElement as the parent.");
    }

    this.#readOnly = readOnly;
    this.#container = Utils.createElement("div", ["row", "g-3"]);
    parentElement.appendChild(this.#container);

    const mode = data?.signalToNoise != null ? "Signal / Noise" : "Time & Count";

    this.#select = this.#createSelect(mode);
    const selectCol = Utils.createElement("div", "col-12");
    selectCol.append(
      this.#createLabel("Exposure Mode", "exposureModeSelect"),
      this.#select
    );

    const sn = data?.signalToNoise?.value ?? "";
    const snWavelength = data?.signalToNoise?.at?.nanometers ?? "";
    this.#snInput = this.#createNumberInput("Signal / Noise", "sn", sn);
    this.#snWavelengthInput = this.#createNumberInput(
      "\u03BB for S/N",
      "snWavelength",
      snWavelength,
      "nm"
    );

    const time = data?.timeAndCount?.time?.seconds ?? "";
    const count = data?.timeAndCount?.count ?? "";
    const tcWavelength = data?.timeAndCount?.at?.nanometers ?? "";
    this.#timeInput = this.#createNumberInput(
      "Exposure Time",
      "exposureTime",
      time,
      "s"
    );
    this.#countInput = this.#createNumberInput(
      "Number of Exposures",
      "numExposures",
      count,
      "#"
    );
    this.#tcWavelengthInput = this.#createNumberInput(
      "\u03BB for Signal / Noise",
      "countWavelength",
      tcWavelength,
      "nm"
    );

    this.#container.append(
      selectCol,
      this.#snInput,
      this.#snWavelengthInput,
      this.#timeInput,
      this.#countInput,
      this.#tcWavelengthInput
    );

    this.#setupListener();
    this.#updateVisibility();
  }

  /**
   * Create the dropdown select for exposure mode.
   * @param {string} value - Initial selection value.
   * @returns {HTMLSelectElement}
   * @private
   */
  #createSelect(value) {
    const select = Utils.createElement("select", "form-select");
    select.id = "exposureModeSelect";
    ["Signal / Noise", "Time & Count"].forEach((opt) => {
      const o = Utils.createElement("option");
      o.value = opt;
      o.textContent = opt;
      if (opt === value) o.selected = true;
      select.append(o);
    });
    select.disabled = this.#readOnly;
    return select;
  }

  /**
   * Create a labeled number input group.
   * @param {string} label - Label text.
   * @param {string} id - ID suffix.
   * @param {string|number} value - Initial value.
   * @param {string} [suffix=""] - Optional suffix text.
   * @returns {HTMLDivElement}
   * @private
   */
  #createNumberInput(label, id, value, suffix = "") {
    const col = Utils.createElement("div", "col-md-6");
    const labelEl = this.#createLabel(label, `${id}Input`);
    const input = Utils.createElement("input", "form-control");
    input.id = `${id}Input`;
    input.type = "number";
    input.value = value;
    if (this.#readOnly) input.disabled = true;

    const group = suffix ? this.#wrapWithInputGroup(input, suffix) : input;
    col.append(labelEl, group);
    return col;
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
   * Set up change listener on dropdown.
   * @private
   */
  #setupListener() {
    this.#select.addEventListener("change", () => this.#updateVisibility());
  }

  /**
   * Toggle input visibility based on selected mode.
   * @private
   */
  #updateVisibility() {
    const mode = this.#select.value;
    const isSN = mode === "Signal / Noise";

    this.#toggleField(this.#snInput, isSN);
    this.#toggleField(this.#snWavelengthInput, isSN);
    this.#toggleField(this.#timeInput, !isSN);
    this.#toggleField(this.#countInput, !isSN);
    this.#toggleField(this.#tcWavelengthInput, !isSN);
  }

  /**
   * Toggle a column’s display using Bootstrap `d-none`.
   * @param {HTMLElement} col - Column element.
   * @param {boolean} show - Whether to show or hide it.
   * @private
   */
  #toggleField(col, show) {
    col.classList.toggle("d-none", !show);
  }

  /**
   * Get current values from the editor.
   * @returns {Object}
   */
  getValues() {
    const mode = this.#select.value;
    if (mode === "Signal / Noise") {
      const sn = parseFloat(this.#snInput.querySelector("input").value);
      const wavelength = parseFloat(
        this.#snWavelengthInput.querySelector("input").value
      );
      return {
        exposureTimeMode: {
          signalToNoise: isNaN(sn)
            ? null
            : { value: sn, at: isNaN(wavelength) ? null : { nanometers: wavelength } },
          timeAndCount: null,
        },
      };
    }

    const time = parseFloat(this.#timeInput.querySelector("input").value);
    const count = parseInt(this.#countInput.querySelector("input").value);
    const wavelength = parseFloat(this.#tcWavelengthInput.querySelector("input").value);
    return {
      exposureTimeMode: {
        signalToNoise: null,
        timeAndCount: {
          time: isNaN(time) ? null : { seconds: time },
          count: isNaN(count) ? null : count,
          at: isNaN(wavelength) ? null : { nanometers: wavelength },
        },
      },
    };
  }

  /**
   * Enable or disable all inputs.
   * @param {boolean} flag - True to disable (readonly), false to enable.
   */
  setReadOnly(flag) {
    this.#readOnly = flag;
    this.#select.disabled = flag;
    for (const col of [
      this.#snInput,
      this.#snWavelengthInput,
      this.#timeInput,
      this.#countInput,
      this.#tcWavelengthInput,
    ]) {
      const input = col.querySelector("input");
      if (input) input.disabled = flag;
    }
  }
}
