/**
 * Class representing an Elevation Range editor (Air Mass or Hour Angle).
 */
class ElevationRangeEditor {
  #container;
  #select;
  #haMinInput;
  #haMaxInput;
  #amMinInput;
  #amMaxInput;
  #readOnly;

  /**
   * Create an elevation range editor and render it into the container.
   * @param {HTMLElement} parentElement - The parent container to render into.
   * @param {Object} [options]
   * @param {Object} [options.data] - Elevation range input data (HA or AM).
   * @param {boolean} [options.readOnly=false] - Whether inputs are readonly.
   */
  // TODO: Should I change the options input to have defaults?
  constructor(parentElement, { data = {}, readOnly = false } = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("ElevationRangeEditor expects an HTMLElement as the parent.");
    }

    this.#readOnly = readOnly;

    this.#container = Utils.createElement("div", ["row", "g-3"]);
    parentElement.appendChild(this.#container);

    // Always default to Air Mass unless HA values are present.
    const mode = data?.hourAngleRange ? "Hour Angle" : "Air Mass";

    // Create select for mode.
    this.#select = this.#createSelect(mode);
    const selectCol = Utils.createElement("div", "col-12");
    selectCol.append(
      this.#createLabel("Elevation Range", "elevationRangeSelect"),
      this.#select
    );

    // Create both sets of inputs with fallback to empty strings.
    const haMin = data?.hourAngleRange?.minHours ?? "";
    const haMax = data?.hourAngleRange?.maxHours ?? "";
    const amMin = data?.airMass?.min ?? "";
    const amMax = data?.airMass?.max ?? "";

    this.#haMinInput = this.#createNumberInput(
      "Hour Angle Minimum",
      "haMinimum",
      haMin,
      "hours"
    );
    this.#haMaxInput = this.#createNumberInput(
      "Hour Angle Maximum",
      "haMaximum",
      haMax,
      "hours"
    );
    this.#amMinInput = this.#createNumberInput(
      "Air Mass Minimum",
      "airMassMinimum",
      amMin
    );
    this.#amMaxInput = this.#createNumberInput(
      "Air Mass Maximum",
      "airMassMaximum",
      amMax
    );

    this.#container.append(
      selectCol,
      this.#haMinInput,
      this.#haMaxInput,
      this.#amMinInput,
      this.#amMaxInput
    );

    this.#setupListener();
    this.#updateVisibility();
  }

  /**
   * Create a select dropdown.
   * @param {string} value - Initial value.
   * @returns {HTMLSelectElement}
   * @private
   */
  #createSelect(value) {
    const select = Utils.createElement("select", "form-select");
    select.id = "elevationRangeSelect";
    ["Hour Angle", "Air Mass"].forEach((opt) => {
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
   * @private
   */
  #createLabel(text, htmlFor) {
    const label = Utils.createElement("label", "form-label");
    label.textContent = text;
    label.htmlFor = htmlFor;
    return label;
  }

  /**
   * Wrap input with suffix text.
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
   * Set up listener to toggle visibility based on selection.
   * @private
   */
  #setupListener() {
    this.#select.addEventListener("change", () => this.#updateVisibility());
  }

  /**
   * Update visibility of Hour Angle and Air Mass fields.
   * @private
   */
  #updateVisibility() {
    const mode = this.#select.value;
    const isHA = mode === "Hour Angle";
    this.#toggleField(this.#haMinInput, isHA);
    this.#toggleField(this.#haMaxInput, isHA);
    this.#toggleField(this.#amMinInput, !isHA);
    this.#toggleField(this.#amMaxInput, !isHA);
  }

  /**
   * Toggle field visibility via Bootstrap `d-none`.
   * @private
   */
  #toggleField(col, show) {
    col.classList.toggle("d-none", !show);
  }

  /**
   * Get the currently selected elevation range values.
   * @returns {Object} - The elevation range data.
   */
  getValues() {
    const mode = this.#select.value;
    if (mode === "Hour Angle") {
      return {
        hourAngleRange: {
          minHours: parseFloat(this.#haMinInput.querySelector("input").value),
          maxHours: parseFloat(this.#haMaxInput.querySelector("input").value),
        },
      };
    }
    return {
      elevationRange: {
        airMass: {
          min: parseFloat(this.#amMinInput.querySelector("input").value),
          max: parseFloat(this.#amMaxInput.querySelector("input").value),
        },
      },
    };
  }

  /**
   * Set readonly/editable mode.
   * @param {boolean} flag - True to set readonly, false to allow editing.
   */
  setReadOnly(flag) {
    this.#readOnly = flag;

    // Update select.
    this.#select.disabled = flag;

    // Update inputs.
    for (const col of [
      this.#haMinInput,
      this.#haMaxInput,
      this.#amMinInput,
      this.#amMaxInput,
    ]) {
      const input = col.querySelector("input");
      if (input) input.disabled = flag;
    }
  }
}
