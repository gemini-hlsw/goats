/**
 * Editor for the spatial offsets of a GMOS long slit observation: q offsets
 * along the slit, or p/q offsets to sky, each with its guide state.
 */
class SpatialOffsetsEditor {
  /** @type {HTMLElement} */
  #container;

  /** @type {string} */
  #idPrefix;

  /** @type {boolean} */
  #readOnly;

  /** @type {string} */
  #mode;

  /** @type {Object<string, Array<{p: number, q: number, enabled: boolean}>>} */
  #offsets;

  /** Lucuma's defaults, for a mode the observation carries no offsets in. */
  static DEFAULT_OFFSETS = {
    NOD_ALONG_SLIT: [
      { p: 0, q: 0, enabled: true },
      { p: 0, q: 15, enabled: true },
      { p: 0, q: -15, enabled: true },
    ],
    NOD_TO_SKY: [{ p: 0, q: 0, enabled: true }],
  };

  /**
   * @param {HTMLElement} parentElement
   * @param {{data?: Object, labelText?: string, idPrefix?: string,
   *     readOnly?: boolean}} [options]
   */
  constructor(
    parentElement,
    {
      data = {},
      labelText = "Spatial Offsets",
      idPrefix = "spatial-offsets",
      readOnly = false,
    } = {},
  ) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("SpatialOffsetsEditor expects an HTMLElement as the parent.");
    }

    this.#idPrefix = idPrefix;
    this.#readOnly = readOnly;
    this.#offsets = Object.fromEntries(
      Object.entries(SpatialOffsetsEditor.DEFAULT_OFFSETS).map(([mode, offsets]) => [
        mode,
        offsets.map((offset) => ({ ...offset })),
      ]),
    );

    // GPP only fills the explicit configs when the user overrode the defaults.
    const configs = data?.explicitTelescopeConfigs ?? data?.defaultTelescopeConfigs;
    this.#mode =
      configs?.offsetMode in Lookups.slitOffsetMode ? configs.offsetMode : "NOD_ALONG_SLIT";
    const offsets = SpatialOffsetsEditor.#parseConfigs(configs);
    if (offsets.length > 0) {
      this.#offsets[this.#mode] = offsets;
    }

    this.#container = Utils.createElement("div", ["d-flex", "flex-column"]);
    parentElement.appendChild(this.#container);
    this.#render(labelText);
  }

  /**
   * Read the offsets of GPP's telescope configs.
   *
   * @private
   * @param {Object=} configs
   * @returns {Array<{p: number, q: number, enabled: boolean}>}
   */
  static #parseConfigs(configs) {
    const enabled = (config) => config.guiding === Lookups.guideState.ENABLED;

    if (configs?.offsetMode === "NOD_TO_SKY") {
      return (configs.toSky ?? []).map((config) => ({
        p: config.offset?.p?.arcseconds ?? 0,
        q: config.offset?.q?.arcseconds ?? 0,
        enabled: enabled(config),
      }));
    }

    return (configs?.alongSlit ?? []).map((config) => ({
      p: 0,
      q: config.q?.arcseconds ?? 0,
      enabled: enabled(config),
    }));
  }

  /**
   * Parse an offset from a string, returning 0 if invalid.
   *
   * @private
   * @param {string} text
   * @returns {number}
   */
  static #parseArcseconds(text) {
    const value = parseFloat(text);
    return Number.isFinite(value) ? value : 0;
  }

  /**
   * Render the component.
   *
   * @private
   * @param {string} labelText
   */
  #render(labelText) {
    const selectId = `${this.#idPrefix}-mode`;

    const label = Utils.createElement("label", ["form-label", "mb-1"]);
    label.htmlFor = selectId;
    label.textContent = labelText;

    const select = Utils.createElement("select", ["form-select"]);
    select.id = selectId;
    select.disabled = this.#readOnly;
    Object.entries(Lookups.slitOffsetMode).forEach(([value, text]) => {
      const option = Utils.createElement("option");
      option.value = value;
      option.textContent = text;
      option.selected = value === this.#mode;
      select.append(option);
    });
    select.addEventListener("change", (event) => {
      this.#mode = event.target.value;
      this.#refreshList();
    });

    const list = Utils.createElement("div", ["d-flex", "flex-column", "gap-2", "mt-2"]);
    list.id = `${this.#idPrefix}-list`;

    const addButton = this.#createButton(
      ["btn", "btn-outline-primary", "align-self-start", "mt-2"],
      `<i class="fa-solid fa-plus"></i> Add`,
      () => {
        this.#offsets[this.#mode].push({ p: 0, q: 0, enabled: true });
        this.#refreshList();
      },
    );

    this.#container.append(label, select, list, addButton);
    this.#refreshList();
  }

  /**
   * Rebuild the offset rows of the current mode.
   *
   * @private
   */
  #refreshList() {
    const list = this.#container.querySelector(`#${this.#idPrefix}-list`);
    if (!list) return;

    list.innerHTML = "";
    this.#offsets[this.#mode].forEach((_, index) => {
      list.append(this.#buildOffsetRow(index));
    });
  }

  /**
   * Build a single offset row: its axes, guide toggle and remove button.
   *
   * @private
   * @param {number} index
   * @returns {HTMLElement}
   */
  #buildOffsetRow(index) {
    const offset = this.#offsets[this.#mode][index];
    const row = Utils.createElement("div", ["d-flex", "align-items-center", "gap-2"]);

    ["p", "q"].forEach((axis) => row.append(this.#buildAxisField(index, axis)));

    const toggleButton = this.#createButton(
      ["btn", "btn-sm", offset.enabled ? "btn-outline-success" : "btn-outline-secondary"],
      `<i class="fa-solid fa-crosshairs"></i>`,
      () => {
        offset.enabled = !offset.enabled;
        this.#refreshList();
      },
    );

    const removeButton = this.#createButton(
      ["btn", "btn-sm", "btn-outline-danger"],
      `<i class="fa-solid fa-minus"></i>`,
      () => {
        if (index === 0) return;
        this.#offsets[this.#mode].splice(index, 1);
        this.#refreshList();
      },
    );

    // GPP needs at least one offset.
    if (index === 0) {
      removeButton.classList.add("invisible");
    }

    row.append(toggleButton, removeButton);
    return row;
  }

  /**
   * Build the input group for one axis of an offset, sized as imaging's.
   *
   * @private
   * @param {number} index
   * @param {"p"|"q"} axis
   * @returns {HTMLElement}
   */
  #buildAxisField(index, axis) {
    const offset = this.#offsets[this.#mode][index];

    const input = Utils.createElement("input", ["form-control"]);
    input.type = "number";
    input.step = "0.01";
    input.id = `${this.#idPrefix}-${axis}-${index}`;
    input.value = Number(offset[axis]).toFixed(2);
    // Along the slit only q moves, so p stays shown but locked at 0.
    input.disabled =
      this.#readOnly || (axis === "p" && this.#mode !== "NOD_TO_SKY");
    input.addEventListener("change", (event) => {
      offset[axis] = SpatialOffsetsEditor.#parseArcseconds(event.target.value);
    });

    const group = Utils.createElement("div", ["input-group"]);
    group.append(this.#buildText(axis), input, this.#buildText("arcsec"));

    const col = Utils.createElement("div", ["col-5"]);
    col.append(group);
    return col;
  }

  /**
   * Return the offsets of the current mode, shaped as GPP's telescope configs.
   *
   * @returns {Object}
   */
  getValues() {
    const offsets = this.#offsets[this.#mode];
    const guiding = (offset) =>
      offset.enabled ? Lookups.guideState.ENABLED : Lookups.guideState.DISABLED;

    if (this.#mode === "NOD_TO_SKY") {
      return {
        offsetMode: this.#mode,
        toSky: offsets.map((offset) => ({
          offset: {
            p: { arcseconds: offset.p },
            q: { arcseconds: offset.q },
          },
          guiding: guiding(offset),
        })),
      };
    }

    return {
      offsetMode: this.#mode,
      alongSlit: offsets.map((offset) => ({
        q: { arcseconds: offset.q },
        guiding: guiding(offset),
      })),
    };
  }

  /**
   * Create an input group text.
   *
   * @private
   * @param {string} text
   * @returns {HTMLElement}
   */
  #buildText(text) {
    const element = Utils.createElement("span", ["input-group-text"]);
    element.textContent = text;
    return element;
  }

  /**
   * Create a button.
   *
   * @private
   * @param {string[]} classes
   * @param {string} html
   * @param {Function} onClick
   * @returns {HTMLButtonElement}
   */
  #createButton(classes, html, onClick) {
    const button = Utils.createElement("button", classes);
    button.type = "button";
    button.innerHTML = html;
    button.disabled = this.#readOnly;
    button.addEventListener("click", onClick);
    return button;
  }
}
