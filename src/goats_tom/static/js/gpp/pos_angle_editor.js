/**
 * Editor for position angle constraints.
 * Mode dropdown + angle input that shows/hides depending on the selected mode.
 *
 * @example
 * const div = Utils.createElement("div", "mt-3");
 * new PosAngleEditor(div, { meta, data: raw ?? {}, readOnly: this.#readOnly });
 */
class PosAngleEditor {
  /** @type {HTMLElement} */
  #container;

  /** @type {object} */
  #meta;

  /** @type {object} */
  #data;

  /** @type {boolean} */
  #readOnly;

  /** Modes that require the angle input to be visible. */
  static #MODES_WITH_ANGLE = ["ALLOW_FLIP", "PARALLACTIC_OVERRIDE", "FIXED"];

  /**
   * @param {HTMLElement} container
   * @param {{ meta?: object, data?: object, readOnly?: boolean }} options
   */
  constructor(container, { meta = {}, data = {}, readOnly = false } = {}) {
    this.#container = container;
    this.#meta = meta;
    this.#data = data;
    this.#readOnly = readOnly;
    this.#render();
  }

  /** Builds the wrapper, mode dropdown, and angle field. Wires the toggle. */
  #render() {
    // Need to wrap to preserve layout and match rest.
    const wrapper = Utils.createElement("div", "mt-3");
    const div = Utils.createElement("div", ["row", "g-3"]);

    const modeField = this.#createCol({
      id: `${this.#meta.id}ModeSelect`,
      labelText: "Position Angle",
      element: "select",
      options: this.#meta.options,
      selectedValue: this.#data?.mode ?? this.#meta.value,
      disabled: this.#readOnly,
    });

    const degrees = this.#data?.angle?.degrees ?? 0;
    const showAngle = PosAngleEditor.#MODES_WITH_ANGLE.includes(this.#data?.mode);

    const angleField = this.#createCol({
      id: `${this.#meta.id}AngleInput`,
      labelText: "\u00A0", // Non-breaking space to align.
      type: "number",
      value: this.#data?.angle?.degrees ?? "",
      suffix: this.#meta.suffix, // "°E of N"
      disabled: this.#readOnly,
      hint: this.#data?.mode === "ALLOW_FLIP" ? degrees : null,
    });

    if (!showAngle) angleField.classList.add("d-none");

    // Update flip hint when angle changes, wrap value between 0-360.
    angleField.querySelector("input")?.addEventListener("input", (e) => {
      let val = parseFloat(e.target.value);
      if (!isNaN(val)) {
        // Wrap around: 361 → 1, -1 → 359.
        val = ((val % 360) + 360) % 360;
        e.target.value = val;
      }
      this.#updateFlipHint(angleField, isNaN(val) ? 0 : val);
    });

    // Toggle angle field and flip hint on mode change.
    modeField.querySelector("select")?.addEventListener("change", (e) => {
      const selected = e.target.value;
      const showAngle = PosAngleEditor.#MODES_WITH_ANGLE.includes(selected);
      angleField.classList.toggle("d-none", !showAngle);

      const hintEl = this.#getHintEl(angleField);
      if (selected === "ALLOW_FLIP") {
        if (!hintEl) {
          const val = parseFloat(angleField.querySelector("input")?.value ?? 0);
          this.#addFlipHint(angleField, isNaN(val) ? 0 : val);
        }
      } else {
        hintEl?.remove();
      }
    });

    div.append(modeField, angleField);
    wrapper.appendChild(div);
    this.#container.appendChild(wrapper);
  }

  /**
   * Calculates the 180° flipped angle text.
   * @param {number} degrees
   * @returns {string}
   */
  #calcFlipHint(degrees) {
    return `Flipped to ${((+degrees + 180) % 360).toFixed(2)}°`;
  }

  /**
   * Returns the hint element inside a col if it exists.
   * @param {HTMLElement} col
   * @returns {HTMLElement|null}
   */
  #getHintEl(col) {
    return col.querySelector(".form-text") ?? null;
  }

  /**
   * Creates and appends a flip hint below the input-group.
   * @param {HTMLElement} col
   * @param {number} degrees
   */
  #addFlipHint(col, degrees) {
    const hintEl = Utils.createElement("div", ["form-text", "text-end"]);
    hintEl.textContent = this.#calcFlipHint(degrees);
    col.querySelector(".input-group")?.after(hintEl);
  }

  /**
   * Updates the flip hint text if it exists.
   * @param {HTMLElement} col
   * @param {number} degrees
   */
  #updateFlipHint(col, degrees) {
    const hintEl = this.#getHintEl(col);
    if (hintEl) hintEl.textContent = this.#calcFlipHint(degrees);
  }

  /**
   * Builds a Bootstrap col with label, optional hint below the input, and optional suffix.
   *
   * @param {{ id: string, labelText: string, element?: string, type?: string,
   *   value?: string|number, suffix?: string, options?: object[], selectedValue?: string,
   *   disabled?: boolean, hint?: number|null }} params
   * @returns {HTMLElement}
   */
  #createCol({
    id,
    labelText,
    element = "input",
    type = "text",
    value = "",
    suffix = null,
    options = [],
    selectedValue = null,
    disabled = false,
    hint = null,
  }) {
    const col = Utils.createElement("div", ["col-md-6"]);

    const label = Utils.createElement("label", ["form-label"]);
    label.htmlFor = id;
    label.innerHTML = labelText;
    col.append(label);

    let control;
    if (element === "select") {
      control = Utils.createElement("select", ["form-select"]);
      options.forEach((opt) => {
        const optionEl = Utils.createElement("option");
        optionEl.value = opt.value;
        optionEl.textContent = opt.labelText;
        if (opt.disabled) optionEl.disabled = true;
        if (opt.value === selectedValue) optionEl.selected = true;
        control.appendChild(optionEl);
      });
    } else {
      control = Utils.createElement("input", ["form-control"]);
      control.type = type;
      control.step = "any"; // Allow decimals.
      control.value = value;
      if (type === "number") {
        control.min = 0;
        control.max = 360;
      }
    }

    control.id = id;
    control.name = id;
    control.disabled = disabled;

    if (suffix) {
      const group = Utils.createElement("div", ["input-group"]);
      const suffixEl = Utils.createElement("span", ["input-group-text"]);
      suffixEl.textContent = suffix;
      group.append(control, suffixEl);
      col.append(group);
    } else {
      col.append(control);
    }

    // Hint renders below the input group, hint is degrees as number.
    if (hint !== null) {
      this.#addFlipHint(col, hint);
    }

    return col;
  }
}
