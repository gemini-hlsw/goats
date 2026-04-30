/**
 * Parse a float from a string, returning 0 if invalid.
 *
 * @param {string} text
 * @returns {number}
 */
function parseFloatSafe(text) {
  const value = parseFloat(text);
  return Number.isFinite(value) ? value : 0;
}

/**
 * Parse an integer from a string, returning 0 if invalid.
 *
 * @param {string} text
 * @returns {number}
 */
function parseIntSafe(text) {
  const value = parseInt(text, 10);
  return Number.isFinite(value) ? value : 0;
}

/**
 * Editor component for managing offset variant configuration.
 */
class OffsetVariantEditor {
  /** @type {HTMLElement} */
  #container;

  /** @type {string} */
  #idPrefix;

  /** @type {string} */
  #currentVariant;

  /** @type {Array<{p: number, q: number, enabled: boolean}>} */
  #explicitOffsets;

  /** @type {Array<{p: number, q: number, enabled: boolean}>} */
  #skyExplicitOffsets;

  static DEFAULT_PRE_IMAGING_OFFSETS = [
    { p: 0.0, q: 0.0 },
    { p: -4.0, q: -6.0 },
    { p: 4.0, q: -6.0 },
    { p: 8.0, q: 0.0 },
  ];

  static OFFSET_MODES = [
    Lookups.gmosImagingOffsets.ENUMERATED,
    Lookups.gmosImagingOffsets.UNIFORM,
    Lookups.gmosImagingOffsets.SPIRAL,
    Lookups.gmosImagingOffsets.RANDOM,
  ];

  /**
   * @param {HTMLElement} parentElement
   * @param {{data?: Object, idPrefix?: string}} [options]
   */
  constructor(
    parentElement,
    { data = {}, idPrefix = "offset-variant", readOnly = false } = {},
  ) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error(
        "OffsetVariantEditor expects an HTMLElement as the parent.",
      );
    }

    this.#idPrefix = idPrefix;
    this.#currentVariant =
      Lookups.gmosImagingOffsetVariant[data?.variantType] ?? Lookups.gmosImagingOffsetVariant.GROUPED;
    
    // NORMAL OFFSETS
    const variantData = data?.[this.#currentVariant];
    const enumeratedValues = variantData?.offsets?.enumerated?.values ?? [];

    this.#explicitOffsets = enumeratedValues.length > 0
      ? enumeratedValues.map(item => ({
          p: item.offset?.p?.arcseconds ?? 0,
          q: item.offset?.q?.arcseconds ?? 0,
          enabled: item.guiding === "ENABLED"
        }))
      : [{ p: 0, q: 0, enabled: true }];

    // SKY OFFSETS
    const skyEnumeratedValues = variantData?.skyOffsets?.enumerated?.values ?? [];
    this.#skyExplicitOffsets = skyEnumeratedValues.length > 0
      ? skyEnumeratedValues.map(item => ({
          p: item.offset?.p?.arcseconds ?? 0,
          q: item.offset?.q?.arcseconds ?? 0,
          enabled: item.guiding === "ENABLED"
        }))
      : [];

    this.#container = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-3",
    ]);

    parentElement.appendChild(this.#container);
    this.#render(data);
  }

  /**
   * Render the component.
   *
   * @private
   * @param {Object} data
   */
  #render(data = {}) {
    this.#container.innerHTML = "";
    this.#container.append(
      this.#buildVariantRow(),
      this.#buildDynamicSection(data),
    );
    this.#bindVariantChange();
    this.#bindOffsetsChange();
    this.#bindSkyOffsetsChange();
  }

  /**
   * Build dynamic section for current variant.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement}
   */
  #buildDynamicSection(data = {}) {
    const section = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-3",
    ]);
    section.dataset.ovDynamic = "1";

    this.#getVariantNodes(data).forEach((node) => section.append(node));
    return section;
  }

  /**
   * Return the nodes for the selected variant.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement[]}
   */
  #getVariantNodes(data = {}) {
    switch (this.#currentVariant) {
      case Lookups.gmosImagingOffsetVariant.PRE_IMAGING:
        return this.#buildPreImagingSection(data);

      case Lookups.gmosImagingOffsetVariant.GROUPED:
        return this.#buildOffsetModeSection(data, true);

      case Lookups.gmosImagingOffsetVariant.INTERLEAVED:
        return this.#buildOffsetModeSection(data, false);

      default:
        return [];
    }
  }

  /**
   * Build variant select row.
   *
   * @private
   * @returns {HTMLElement}
   */
  #buildVariantRow() {
    return this.#buildRow([
      this.#buildSelectField({
        colClass: "col-12",
        label: "Offset Variant",
        id: `${this.#idPrefix}-variant`,
        name: "offsetVariant",
        options: Object.values(Lookups.gmosImagingOffsetVariant),
        value: this.#currentVariant,
      }),
    ]);
  }

  /**
   * Build pre-imaging section.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement[]}
   */
  #buildPreImagingSection(data = {}) {
    let offsets = data?.preImaging?.values ?? 
                  OffsetVariantEditor.DEFAULT_PRE_IMAGING_OFFSETS;

    if (offsets && typeof offsets === 'object' && !Array.isArray(offsets)) {
      offsets = Object.values(offsets).map(item => ({
        p: item.offset?.p?.arcseconds ?? item.p ?? 0,
        q: item.offset?.q?.arcseconds ?? item.q ?? 0
      }));
    }

    return [
      this.#buildPreImagingOffsets(offsets),
    ];
  }

  /**
   * Build grouped/interleaved shared section.
   *
   * @private
   * @param {Object} data
   * @param {boolean} includeWavelengthOrder
   * @returns {HTMLElement[]}
   */
  #buildOffsetModeSection(data = {}, includeWavelengthOrder = false) {
    return [
      this.#buildOffsetHeaderRow(data, includeWavelengthOrder),
      this.#buildExplicitBlock(data),
      this.#buildUniformBlock(data),
      this.#buildSpiralBlock(data),
      this.#buildRandomBlock(data),
      this.#buildSkyOffsetRow(data),
      this.#buildSkyExplicitBlock(data),
      this.#buildSkyUniformBlock(data),
      this.#buildSkySpiralBlock(data),
      this.#buildSkyRandomBlock(data),
    ];
  }

  /**
   * Build the header row with offsets and optional wavelength order.
   *
   * @private
   * @param {Object} data
   * @param {boolean} includeWavelengthOrder
   * @returns {HTMLElement}
   */
  #buildOffsetHeaderRow(data = {}, includeWavelengthOrder = false) {
    const currentVariantData = data?.[this.#currentVariant];
    const generatorType = currentVariantData?.offsets?.generatorType ?? Lookups.gmosImagingOffsets.NONE;

    const fields = [
      this.#buildSelectField({
        colClass: "col-6",
        label: "Offsets",
        id: `${this.#idPrefix}-offsets`,
        name: "offsets",
        options: Object.values(Lookups.gmosImagingOffsets),
        value: Lookups.gmosImagingOffsets[generatorType] ?? generatorType,
      }),
    ];

    if (includeWavelengthOrder) {
      const wavelengthOrder = currentVariantData?.order ?? Lookups.gmosImagingWavelengthOrder.INCREASING;
      
      fields.push(
        this.#buildSelectField({
          colClass: "col-6",
          label: "Wavelength Order",
          id: `${this.#idPrefix}-wavelength-order`,
          name: "wavelengthOrder",
          options: Object.values(Lookups.gmosImagingWavelengthOrder),
          value: Lookups.gmosImagingWavelengthOrder[wavelengthOrder] ?? wavelengthOrder,
        }),
      );
    }

    return this.#buildRow(fields);
  }

  /**
   * Build pre-imaging offsets list (compact format without offset labels).
   *
   * @private
   * @param {Array<{p: number, q: number}>} offsets
   * @returns {HTMLElement}
   */
  #buildPreImagingOffsets(offsets) {
    const wrapper = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-1",
    ]);

    offsets.forEach((offset, index) => {
      wrapper.append(
        this.#buildPQInputRow({
          pId: `${this.#idPrefix}-offset-${index + 1}-p`,
          pName: `offset-p-${index + 1}`,
          pValue: offset.p,
          qId: `${this.#idPrefix}-offset-${index + 1}-q`,
          qName: `offset-q-${index + 1}`,
          qValue: offset.q,
        }),
      );
    });

    return wrapper;
  }

  /**
   * Build sky offset row (selector y contador).
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement}
   */
  #buildSkyOffsetRow(data = {}) {
    const currentVariantData = data?.[this.#currentVariant];
    const skyCount = currentVariantData?.skyCount ?? 0;
    const skyOffsetsGeneratorType = currentVariantData?.skyOffsets?.generatorType ?? Lookups.gmosImagingOffsets.NONE;

    const skyCountField = this.#buildNumberField({
      colClass: "col-6",
      label: "Sky Offset Count",
      id: `${this.#idPrefix}-sky-offset-count`,
      name: "skyOffsetCount",
      value: skyCount,
      min: 0,
      disabled: skyOffsetsGeneratorType === Lookups.gmosImagingOffsets.NONE,
    });

    // Add listener to remove excess offsets when count decreases
    const skyCountInput = skyCountField.querySelector("input");
    if (skyCountInput) {
      skyCountInput.addEventListener("change", (e) => {
        const newCount = parseIntSafe(e.target.value);
        const maxOffsets = newCount * 2;
        
        // If there are more offsets than allowed, remove the excess
        if (this.#skyExplicitOffsets.length > maxOffsets) {
          this.#skyExplicitOffsets.splice(maxOffsets);
          this.#refreshSkyExplicitList();
        }
      });
    }

    return this.#buildRow([
      skyCountField,
      this.#buildSelectField({
        colClass: "col-6",
        label: "Sky Offsets",
        id: `${this.#idPrefix}-sky-offsets`,
        name: "skyOffsets",
        options: Object.values(Lookups.gmosImagingOffsets),
        value: Lookups.gmosImagingOffsets[skyOffsetsGeneratorType] ?? skyOffsetsGeneratorType,
        disabled: true,
      }),
    ]);
  }

  /**
   * Build sky explicit offsets block.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement}
   */
  #buildSkyExplicitBlock(data = {}) {
    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
    ]);
    block.id = `${this.#idPrefix}-sky-${Lookups.gmosImagingOffsets.ENUMERATED}-block`;

    if (!this.#isSkyOffsetMode(data, Lookups.gmosImagingOffsets.ENUMERATED)) {
      block.classList.add("d-none");
    }

    block.append(this.#buildSkyExplicitOffsetsList());

    const addButton = this.#createButton(
      ["btn", "btn-outline-primary", "align-self-start"],
      `<i class="fa-solid fa-plus"></i> Add`,
      () => {
        const skyCount = parseIntSafe(
          this.#container.querySelector(
            `#${this.#idPrefix}-sky-offset-count`,
          )?.value ?? "0",
        );
        
        if (this.#skyExplicitOffsets.length < skyCount * 2) {
          this.#skyExplicitOffsets.push({ p: 0, q: 0, enabled: true });
          this.#refreshSkyExplicitList();
        }
      },
    );

    block.append(addButton);
    return block;
  }

  /**
   * Build sky explicit offsets list.
   *
   * @private
   * @returns {HTMLElement}
   */
  #buildSkyExplicitOffsetsList() {
    const wrapper = this.#createElement("div");
    wrapper.id = `${this.#idPrefix}-sky-explicit-list`;

    this.#skyExplicitOffsets.forEach((_, index) => {
      wrapper.append(this.#buildSkyExplicitOffsetRow(index));
    });

    return wrapper;
  }

  /**
   * Build a single sky explicit offset row.
   *
   * @private
   * @param {number} index
   * @returns {HTMLElement}
   */
  #buildSkyExplicitOffsetRow(index) {
    const offset = this.#skyExplicitOffsets[index];
    const wrapper = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
      "mb-2",
    ]);

    // Row with P, Q fields and buttons inline
    const row = this.#createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
    ]);

    // P field (sin label)
    const pField = this.#buildPQField({
      colClass: "col-5",
      axis: "p",
      id: `${this.#idPrefix}-sky-explicit-p-${index}`,
      name: `sky-explicit-p-${index}`,
      value: offset.p,
    });
    pField.querySelector("input").addEventListener("change", (event) => {
      this.#skyExplicitOffsets[index].p = parseFloatSafe(event.target.value);
    });

    // Q field (sin label)
    const qField = this.#buildPQField({
      colClass: "col-5",
      axis: "q",
      id: `${this.#idPrefix}-sky-explicit-q-${index}`,
      name: `sky-explicit-q-${index}`,
      value: offset.q,
    });
    qField.querySelector("input").addEventListener("change", (event) => {
      this.#skyExplicitOffsets[index].q = parseFloatSafe(event.target.value);
    });

    // Buttons container
    const buttonsDiv = this.#createElement("div", ["d-flex", "gap-2"]);

    const toggleButton = this.#createButton(
      [
        "btn",
        "btn-sm",
        offset.enabled ? "btn-outline-success" : "btn-outline-secondary",
      ],
      `<i class="fa-solid fa-crosshairs"></i>`,
      () => {
        this.#skyExplicitOffsets[index].enabled = !this.#skyExplicitOffsets[index].enabled;
        this.#refreshSkyExplicitList();
      },
    );

    const removeButton = this.#createButton(
      ["btn", "btn-sm", "btn-outline-danger"],
      `<i class="fa-solid fa-minus"></i>`,
      () => {
        if (index === 0) return;
        this.#skyExplicitOffsets.splice(index, 1);
        this.#refreshSkyExplicitList();
      },
    );

    if (index === 0) {
      removeButton.classList.add("invisible");
    }

    buttonsDiv.append(toggleButton, removeButton);
    row.append(pField, qField, buttonsDiv);
    wrapper.append(row);
    return wrapper;
  }

  /**
   * Refresh sky explicit offsets list.
   *
   * @private
   */
  #refreshSkyExplicitList() {
    const list = this.#container.querySelector(
      `#${this.#idPrefix}-sky-explicit-list`,
    );
    if (!list) return;

    list.innerHTML = "";
    this.#skyExplicitOffsets.forEach((_, index) => {
      list.append(this.#buildSkyExplicitOffsetRow(index));
    });
  }

  /**
   * Build sky uniform block.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement}
   */
  #buildSkyUniformBlock(data = {}) {
    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
    ]);
    block.id = `${this.#idPrefix}-sky-${Lookups.gmosImagingOffsets.UNIFORM}-block`;

    if (!this.#isSkyOffsetMode(data, Lookups.gmosImagingOffsets.UNIFORM)) {
      block.classList.add("d-none");
    }

    const currentVariantData = data?.[this.#currentVariant];
    const skyUniformData = currentVariantData?.skyOffsets?.uniform;

    [
      {
        label: "Corner A",
        pKey: "skyUniformCornerAP",
        qKey: "skyUniformCornerAQ",
        pValue: skyUniformData?.cornerA?.p?.arcseconds ?? 0,
        qValue: skyUniformData?.cornerA?.q?.arcseconds ?? 0,
      },
      {
        label: "Corner B",
        pKey: "skyUniformCornerBP",
        qKey: "skyUniformCornerBQ",
        pValue: skyUniformData?.cornerB?.p?.arcseconds ?? 0,
        qValue: skyUniformData?.cornerB?.q?.arcseconds ?? 0,
      },
    ].forEach(({ label, pKey, qKey, pValue, qValue }) => {
      const row = this.#createElement("div", [
        "d-flex",
        "flex-column",
        "gap-1",
      ]);

      const rowLabel = this.#createElement("label", ["form-label", "mb-0"]);
      rowLabel.textContent = label;

      row.append(
        rowLabel,
        this.#buildPQInputRow({
          pId: `${this.#idPrefix}-${pKey}`,
          pName: pKey,
          pValue,
          qId: `${this.#idPrefix}-${qKey}`,
          qName: qKey,
          qValue,
        }),
      );

      block.append(row);
    });

    return block;
  }

  /**
   * Build sky spiral block.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement}
   */
  #buildSkySpiralBlock(data = {}) {
    const currentVariantData = data?.[this.#currentVariant];
    const spiralData = currentVariantData?.skyOffsets?.spiral;
    const spiralSize = spiralData?.size?.arcseconds ?? 0;
    const centerP = spiralData?.center?.p?.arcseconds ?? 0;
    const centerQ = spiralData?.center?.q?.arcseconds ?? 0;

    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
    ]);
    block.id = `${this.#idPrefix}-sky-${Lookups.gmosImagingOffsets.SPIRAL}-block`;

    if (!this.#isSkyOffsetMode(data, Lookups.gmosImagingOffsets.SPIRAL)) {
      block.classList.add("d-none");
    }

    // Single row with Size, Center P, Center Q
    block.append(
      this.#buildRow([
        this.#buildNumberField({
          colClass: "col-4",
          label: "Size",
          id: `${this.#idPrefix}-sky-spiral-size`,
          name: "skySpiralSize",
          value: spiralSize,
          min: 0,
          step: 0.01,
          suffix: "arcsec",
        }),
        this.#buildPQField({
          colClass: "col-4",
          axis: "p",
          id: `${this.#idPrefix}-sky-spiral-center-p`,
          name: "skySpiralCenterP",
          value: centerP,
          label: "Center P",
        }),
        this.#buildPQField({
          colClass: "col-4",
          axis: "q",
          id: `${this.#idPrefix}-sky-spiral-center-q`,
          name: "skySpiralCenterQ",
          value: centerQ,
          label: "Center Q",
        }),
      ]),
    );

    return block;
  }

  /**
   * Build sky random block.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement}
   */
  #buildSkyRandomBlock(data = {}) {
    const currentVariantData = data?.[this.#currentVariant];
    const randomData = currentVariantData?.skyOffsets?.random;
    const randomSize = randomData?.size?.arcseconds ?? 0;
    const centerP = randomData?.center?.p?.arcseconds ?? 0;
    const centerQ = randomData?.center?.q?.arcseconds ?? 0;

    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
    ]);
    block.id = `${this.#idPrefix}-sky-${Lookups.gmosImagingOffsets.RANDOM}-block`;

    if (!this.#isSkyOffsetMode(data, Lookups.gmosImagingOffsets.RANDOM)) {
      block.classList.add("d-none");
    }

    // Single row with Size, Center P, Center Q
    block.append(
      this.#buildRow([
        this.#buildNumberField({
          colClass: "col-4",
          label: "Size",
          id: `${this.#idPrefix}-sky-random-size`,
          name: "skyRandomSize",
          value: randomSize,
          min: 0,
          step: 0.01,
          suffix: "arcsec",
        }),
        this.#buildPQField({
          colClass: "col-4",
          axis: "p",
          id: `${this.#idPrefix}-sky-random-center-p`,
          name: "skyRandomCenterP",
          value: centerP,
          label: "Center P",
        }),
        this.#buildPQField({
          colClass: "col-4",
          axis: "q",
          id: `${this.#idPrefix}-sky-random-center-q`,
          name: "skyRandomCenterQ",
          value: centerQ,
          label: "Center Q",
        }),
      ]),
    );

    return block;
  }

  /**
   * Build sky size block for spiral/random modes.
   *
   * @private
   * @param {Object} options
   * @returns {HTMLElement}
   */
  #buildSkySizeBlock({ data, mode, id, name, value }) {
    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-1",
    ]);
    block.id = `${this.#idPrefix}-sky-${mode}-block`;

    if (!this.#isSkyOffsetMode(data, mode)) {
      block.classList.add("d-none");
    }

    block.append(
      this.#buildNumberField({
        colClass: "col-4",
        label: "Size",
        id,
        name,
        value,
        min: 0,
        step: 0.01,
        suffix: "arcsec",
      }),
    );

    return block;
  }

  /**
   * Check whether sky offset matches the requested mode.
   *
   * @private
   * @param {Object} data
   * @param {string} mode
   * @returns {boolean}
   */
  #isSkyOffsetMode(data, mode) {
    const currentVariantData = data?.[this.#currentVariant];
    const skyGeneratorType = currentVariantData?.skyOffsets?.generatorType ?? Lookups.gmosImagingOffsets.NONE;
    const skyGeneratorTypeValue = Lookups.gmosImagingOffsets[skyGeneratorType] ?? skyGeneratorType;
    return skyGeneratorTypeValue === mode;
  }

  // ============ NORMAL OFFSETS ============

  /**
   * Build explicit offsets block.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement}
   */
  #buildExplicitBlock(data = {}) {
    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
    ]);
    block.id = `${this.#idPrefix}-${Lookups.gmosImagingOffsets.ENUMERATED}-block`;

    if (!this.#isOffsetMode(data, Lookups.gmosImagingOffsets.ENUMERATED)) {
      block.classList.add("d-none");
    }

    block.append(this.#buildExplicitOffsetsList());

    const addButton = this.#createButton(
      ["btn", "btn-outline-primary", "align-self-start"],
      `<i class="fa-solid fa-plus"></i> Add`,
      () => {
        this.#explicitOffsets.push({ p: 0, q: 0, enabled: true });
        this.#refreshExplicitList();
      },
    );

    block.append(addButton);
    return block;
  }

  /**
   * Build explicit offsets list.
   *
   * @private
   * @returns {HTMLElement}
   */
  #buildExplicitOffsetsList() {
    const wrapper = this.#createElement("div");
    wrapper.id = `${this.#idPrefix}-explicit-list`;

    this.#explicitOffsets.forEach((_, index) => {
      wrapper.append(this.#buildExplicitOffsetRow(index));
    });

    return wrapper;
  }

  /**
   * Build a single explicit offset row.
   *
   * @private
   * @param {number} index
   * @returns {HTMLElement}
   */
  #buildExplicitOffsetRow(index) {
    const offset = this.#explicitOffsets[index];
    const wrapper = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
      "mb-2",
    ]);

    // Row with P, Q fields and buttons inline
    const row = this.#createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
    ]);

    // P field (sin label)
    const pField = this.#buildPQField({
      colClass: "col-5",
      axis: "p",
      id: `${this.#idPrefix}-explicit-p-${index}`,
      name: `explicit-p-${index}`,
      value: offset.p,
    });
    pField.querySelector("input").addEventListener("change", (event) => {
      this.#explicitOffsets[index].p = parseFloatSafe(event.target.value);
    });

    // Q field (sin label)
    const qField = this.#buildPQField({
      colClass: "col-5",
      axis: "q",
      id: `${this.#idPrefix}-explicit-q-${index}`,
      name: `explicit-q-${index}`,
      value: offset.q,
    });
    qField.querySelector("input").addEventListener("change", (event) => {
      this.#explicitOffsets[index].q = parseFloatSafe(event.target.value);
    });

    // Buttons container
    const buttonsDiv = this.#createElement("div", ["d-flex", "gap-2"]);

    const toggleButton = this.#createButton(
      [
        "btn",
        "btn-sm",
        offset.enabled ? "btn-outline-success" : "btn-outline-secondary",
      ],
      `<i class="fa-solid fa-crosshairs"></i>`,
      () => {
        this.#explicitOffsets[index].enabled = !this.#explicitOffsets[index].enabled;
        this.#refreshExplicitList();
      },
    );

    const removeButton = this.#createButton(
      ["btn", "btn-sm", "btn-outline-danger"],
      `<i class="fa-solid fa-minus"></i>`,
      () => {
        if (index === 0) return;
        this.#explicitOffsets.splice(index, 1);
        this.#refreshExplicitList();
      },
    );

    if (index === 0) {
      removeButton.classList.add("invisible");
    }

    buttonsDiv.append(toggleButton, removeButton);
    row.append(pField, qField, buttonsDiv);
    wrapper.append(row);
    return wrapper;
  }

  /**
   * Refresh explicit offsets list.
   *
   * @private
   */
  #refreshExplicitList() {
    const list = this.#container.querySelector(
      `#${this.#idPrefix}-explicit-list`,
    );
    if (!list) return;

    list.innerHTML = "";
    this.#explicitOffsets.forEach((_, index) => {
      list.append(this.#buildExplicitOffsetRow(index));
    });
  }

  /**
   * Build uniform block.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement}
   */
  #buildUniformBlock(data = {}) {
    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
    ]);
    block.id = `${this.#idPrefix}-${Lookups.gmosImagingOffsets.UNIFORM}-block`;

    if (!this.#isOffsetMode(data, Lookups.gmosImagingOffsets.UNIFORM)) {
      block.classList.add("d-none");
    }

    const currentVariantData = data?.[this.#currentVariant];
    const uniformData = currentVariantData?.offsets?.uniform;

    [
      {
        label: "Corner A",
        pKey: "uniformCornerAP",
        qKey: "uniformCornerAQ",
        pValue: uniformData?.cornerA?.p?.arcseconds ?? 0,
        qValue: uniformData?.cornerA?.q?.arcseconds ?? 0,
      },
      {
        label: "Corner B",
        pKey: "uniformCornerBP",
        qKey: "uniformCornerBQ",
        pValue: uniformData?.cornerB?.p?.arcseconds ?? 0,
        qValue: uniformData?.cornerB?.q?.arcseconds ?? 0,
      },
    ].forEach(({ label, pKey, qKey, pValue, qValue }) => {
      const row = this.#createElement("div", [
        "d-flex",
        "flex-column",
        "gap-1",
      ]);

      const rowLabel = this.#createElement("label", ["form-label", "mb-0"]);
      rowLabel.textContent = label;

      row.append(
        rowLabel,
        this.#buildPQInputRow({
          pId: `${this.#idPrefix}-${pKey}`,
          pName: pKey,
          pValue,
          qId: `${this.#idPrefix}-${qKey}`,
          qName: qKey,
          qValue,
        }),
      );

      block.append(row);
    });

    return block;
  }

  /**
   * Build spiral block.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement}
   */
  #buildSpiralBlock(data = {}) {
    const currentVariantData = data?.[this.#currentVariant];
    const spiralData = currentVariantData?.offsets?.spiral;
    const spiralSize = spiralData?.size?.arcseconds ?? 0;

    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
    ]);
    block.id = `${this.#idPrefix}-${Lookups.gmosImagingOffsets.SPIRAL}-block`;

    if (!this.#isOffsetMode(data, Lookups.gmosImagingOffsets.SPIRAL)) {
      block.classList.add("d-none");
    }

    // Size only
    block.append(
      this.#buildNumberField({
        colClass: "col-4",
        label: "Size",
        id: `${this.#idPrefix}-spiral-size`,
        name: "spiralSize",
        value: spiralSize,
        min: 0,
        step: 0.01,
        suffix: "arcsec",
      }),
    );

    return block;
  }

  /**
   * Build random block.
   *
   * @private
   * @param {Object} data
   * @returns {HTMLElement}
   */
  #buildRandomBlock(data = {}) {
    const currentVariantData = data?.[this.#currentVariant];
    const randomData = currentVariantData?.offsets?.random;
    const randomSize = randomData?.size?.arcseconds ?? 0;

    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-2",
    ]);
    block.id = `${this.#idPrefix}-${Lookups.gmosImagingOffsets.RANDOM}-block`;

    if (!this.#isOffsetMode(data, Lookups.gmosImagingOffsets.RANDOM)) {
      block.classList.add("d-none");
    }

    // Size only
    block.append(
      this.#buildNumberField({
        colClass: "col-4",
        label: "Size",
        id: `${this.#idPrefix}-random-size`,
        name: "randomSize",
        value: randomSize,
        min: 0,
        step: 0.01,
        suffix: "arcsec",
      }),
    );

    return block;
  }

  /**
   * Build size block for spiral/random modes.
   *
   * @private
   * @param {Object} options
   * @returns {HTMLElement}
   */
  #buildSizeBlock({ data, mode, id, name, value }) {
    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-1",
    ]);
    block.id = `${this.#idPrefix}-${mode}-block`;

    if (!this.#isOffsetMode(data, mode)) {
      block.classList.add("d-none");
    }

    block.append(
      this.#buildNumberField({
        colClass: "col-4",
        label: "Size",
        id,
        name,
        value,
        min: 0,
        step: 0.01,
        suffix: "arcsec",
      }),
    );

    return block;
  }

  /**
   * Check whether data matches the requested offset mode.
   *
   * @private
   * @param {Object} data
   * @param {string} mode
   * @returns {boolean}
   */
  #isOffsetMode(data, mode) {
    const currentVariantData = data?.[this.#currentVariant];
    const generatorType = currentVariantData?.offsets?.generatorType ?? Lookups.gmosImagingOffsets.NONE;
    const generatorTypeValue = Lookups.gmosImagingOffsets[generatorType] ?? generatorType;
    return generatorTypeValue === mode;
  }

  /**
   * Build a section divider with title.
   *
   * @private
   * @param {string} title
   * @returns {HTMLElement}
   */
  #buildSectionDivider(title) {
    const divider = this.#createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
      "mt-3",
      "mb-2",
    ]);

    const line = this.#createElement("div", ["flex-grow-1"]);
    line.style.borderTop = "1px solid var(--bs-border-color)";

    const titleEl = this.#createElement("span", ["text-muted", "small", "fw-semibold"]);
    titleEl.textContent = title;

    divider.append(line, titleEl);
    return divider;
  }

  /**
   * Build a row container.
   *
   * @private
   * @param {HTMLElement[]} children
   * @returns {HTMLElement}
   */
  #buildRow(children = []) {
    const row = this.#createElement("div", ["row", "g-3"]);
    children.forEach((child) => row.append(child));
    return row;
  }

  /**
   * Build a select field.
   *
   * @private
   * @param {Object} config
   * @returns {HTMLElement}
   */
  #buildSelectField({
    colClass = "col-12",
    label,
    id,
    name,
    options = [],
    value = "",
    disabled = false,
  }) {
    const select = this.#createElement("select", ["form-select"]);
    select.id = id;
    select.name = name;
    select.disabled = disabled;

    options.forEach((optionValue) => {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = Formatters.capitalizeFirstLetter(optionValue);
      option.selected = optionValue === value;
      select.append(option);
    });

    return this.#buildField({
      colClass,
      label,
      id,
      control: select,
    });
  }

  /**
   * Build a numeric field.
   *
   * @private
   * @param {Object} config
   * @returns {HTMLElement}
   */
  #buildNumberField({
    colClass = "col-12",
    label,
    id,
    name,
    value = 0,
    min = null,
    step = null,
    suffix = "",
    disabled = false,
  }) {
    const input = this.#createElement("input", ["form-control"]);
    input.type = "number";
    input.id = id;
    input.name = name;
    input.value = value;
    input.disabled = disabled;

    if (min !== null) input.min = String(min);
    if (step !== null) input.step = String(step);

    const control = suffix
      ? this.#buildInputGroup([input, this.#buildText("span", suffix, ["input-group-text"])])
      : input;

    return this.#buildField({
      colClass,
      label,
      id,
      control,
    });
  }

  /**
   * Build a labeled field.
   *
   * @private
   * @param {Object} config
   * @returns {HTMLElement}
   */
  #buildField({ colClass, label, id, control }) {
    const col = this.#createElement("div", [colClass]);
    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-1",
    ]);
    const fieldLabel = this.#createElement("label", ["form-label", "mb-0"]);
    fieldLabel.textContent = label;
    fieldLabel.setAttribute("for", id);

    block.append(fieldLabel, control);
    col.append(block);
    return col;
  }

  /**
   * Build a p/q row.
   *
   * @private
   * @param {Object} config
   * @returns {HTMLElement}
   */
  #buildPQInputRow({
    pId,
    pName,
    pValue = 0,
    qId,
    qName,
    qValue = 0,
  }) {
    return this.#buildRow([
      this.#buildPQField({
        colClass: "col-6",
        axis: "p",
        id: pId,
        name: pName,
        value: pValue,
      }),
      this.#buildPQField({
        colClass: "col-6",
        axis: "q",
        id: qId,
        name: qName,
        value: qValue,
      }),
    ]);
  }

  /**
   * Build a p/q field.
   *
   * @private
   * @param {Object} config
   * @returns {HTMLElement}
   */
  /**
   * Build a p/q field.
   *
   * @private
   * @param {Object} config
   * @returns {HTMLElement}
   */
  #buildPQField({ colClass = "col-6", axis, id, name, value = 0, label = null }) {
    const input = this.#createElement("input", ["form-control"]);
    input.type = "number";
    input.step = "0.01";
    input.id = id;
    input.name = name;
    input.value = Number(value).toFixed(2);

    const control = this.#buildInputGroup([
      this.#buildText("span", axis, ["input-group-text"]),
      input,
      this.#buildText("span", "arcsec", ["input-group-text"]),
    ]);

    const col = this.#createElement("div", [colClass]);
    const block = this.#createElement("div", [
      "d-flex",
      "flex-column",
      "gap-1",
    ]);
    
    if (label) {
      const fieldLabel = this.#createElement("label", ["form-label", "mb-0"]);
      fieldLabel.textContent = label;
      fieldLabel.setAttribute("for", id);
      block.append(fieldLabel);
    }
    
    block.append(control);
    col.append(block);
    return col;
  }

  /**
   * Build inline p/q input group for explicit offsets.
   *
   * @private
   * @param {Object} config
   * @returns {HTMLElement}
   */
  #buildPQInlineGroup({
    pName,
    pValue = 0,
    qName,
    qValue = 0,
    onPChange,
    onQChange,
  }) {
    const pInput = this.#createElement("input", ["form-control"]);
    pInput.type = "number";
    pInput.step = "0.01";
    pInput.name = pName;
    pInput.value = Number(pValue).toFixed(2);
    pInput.addEventListener("change", (event) => {
      onPChange(parseFloatSafe(event.target.value));
    });

    const qInput = this.#createElement("input", ["form-control"]);
    qInput.type = "number";
    qInput.step = "0.01";
    qInput.name = qName;
    qInput.value = Number(qValue).toFixed(2);
    qInput.addEventListener("change", (event) => {
      onQChange(parseFloatSafe(event.target.value));
    });

    return this.#buildInputGroup([
      this.#buildText("span", "p", ["input-group-text"]),
      pInput,
      this.#buildText("span", "q", ["input-group-text"]),
      qInput,
      this.#buildText("span", "arcsec", ["input-group-text"]),
    ]);
  }

  /**
   * Build bootstrap input-group container.
   *
   * @private
   * @param {HTMLElement[]} children
   * @returns {HTMLElement}
   */
  #buildInputGroup(children = []) {
    const group = this.#createElement("div", ["input-group"]);
    children.forEach((child) => group.append(child));
    return group;
  }

  /**
   * Toggle offset mode blocks.
   *
   * @private
   * @param {string} selectedMode
   */
  #toggleOffsetBlocks(selectedMode) {
    OffsetVariantEditor.OFFSET_MODES.forEach((mode) => {
      const block = this.#container.querySelector(
        `#${this.#idPrefix}-${mode}-block`,
      );
      if (!block) return;

      block.classList.toggle("d-none", mode !== selectedMode);
    });
  }

  /**
   * Toggle sky offset mode blocks.
   *
   * @private
   * @param {string} selectedMode
   */
  #toggleSkyOffsetBlocks(selectedMode) {
    OffsetVariantEditor.OFFSET_MODES.forEach((mode) => {
      const block = this.#container.querySelector(
        `#${this.#idPrefix}-sky-${mode}-block`,
      );
      if (!block) return;

      block.classList.toggle("d-none", mode !== selectedMode);
    });

    // Enable/disable sky count
    const skyCountField = this.#container.querySelector(
      `#${this.#idPrefix}-sky-offset-count`,
    );
    if (skyCountField) {
      skyCountField.disabled = selectedMode === Lookups.gmosImagingOffsets.NONE;
    }
  }

  /**
   * Bind offsets select changes.
   *
   * @private
   */
  #bindOffsetsChange() {
    this.#container.querySelectorAll('[name="offsets"]').forEach((select) => {
      select.addEventListener("change", (event) => {
        this.#toggleOffsetBlocks(event.target.value);
      });
    });
  }

  /**
   * Bind sky offsets select changes.
   *
   * @private
   */
  #bindSkyOffsetsChange() {
    this.#container.querySelectorAll('[name="skyOffsets"]').forEach((select) => {
      select.addEventListener("change", (event) => {
        this.#toggleSkyOffsetBlocks(event.target.value);
      });
    });
  }

  /**
   * Bind variant select changes.
   *
   * @private
   */
  #bindVariantChange() {
    const variantSelect = this.#container.querySelector(
      `#${this.#idPrefix}-variant`,
    );
    if (!variantSelect) return;

    variantSelect.addEventListener("change", (event) => {
      this.#currentVariant = event.target.value;

      const dynamic = this.#container.querySelector("[data-ov-dynamic]");
      if (!dynamic) return;

      dynamic.innerHTML = "";
      this.#getVariantNodes().forEach((node) => dynamic.append(node));
      this.#bindOffsetsChange();
      this.#bindSkyOffsetsChange();
    });
  }

  /**
   * Return the current editor values.
   *
   * @returns {Object}
   */
  getValues() {
    const variant =
      this.#container.querySelector(`#${this.#idPrefix}-variant`)?.value ??
      Lookups.gmosImagingOffsetVariant.GROUPED;

    if (variant === Lookups.gmosImagingOffsetVariant.PRE_IMAGING) {
      const offsets = Array.from({ length: 4 }, (_, index) => ({
        p: parseFloatSafe(
          this.#container.querySelector(
            `#${this.#idPrefix}-offset-${index + 1}-p`,
          )?.value ?? "",
        ),
        q: parseFloatSafe(
          this.#container.querySelector(
            `#${this.#idPrefix}-offset-${index + 1}-q`,
          )?.value ?? "",
        ),
      }));

      return {
        variant,
        offsets,
      };
    }

    const values = {
      variant,
      offsets:
        this.#container.querySelector(`#${this.#idPrefix}-offsets`)?.value ??
        null,
      skyOffsetCount: parseIntSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-sky-offset-count`,
        )?.value ?? "0",
      ),
      skyOffsets:
        this.#container.querySelector(`#${this.#idPrefix}-sky-offsets`)?.value ??
        null,
    };

    if (values.offsets === Lookups.gmosImagingOffsets.ENUMERATED) {
      values.explicitOffsets = this.#explicitOffsets.map((offset) => ({
        guiding: offset.enabled ? "ENABLED" : "DISABLED",
        offset: {
          p: { arcseconds: offset.p },
          q: { arcseconds: offset.q }
        }
      }));
    }

    if (values.offsets === Lookups.gmosImagingOffsets.UNIFORM) {
      values.uniformCornerAP = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-uniformCornerAP`,
        )?.value ?? "",
      );
      values.uniformCornerAQ = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-uniformCornerAQ`,
        )?.value ?? "",
      );
      values.uniformCornerBP = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-uniformCornerBP`,
        )?.value ?? "",
      );
      values.uniformCornerBQ = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-uniformCornerBQ`,
        )?.value ?? "",
      );
    }

    if (values.offsets === Lookups.gmosImagingOffsets.SPIRAL) {
      values.spiralSize = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-spiral-size`,
        )?.value ?? "",
      );
    }

    if (values.offsets === Lookups.gmosImagingOffsets.RANDOM) {
      values.randomSize = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-random-size`,
        )?.value ?? "",
      );
    }

    // SKY OFFSETS
    if (values.skyOffsets === Lookups.gmosImagingOffsets.ENUMERATED) {
      values.skyExplicitOffsets = this.#skyExplicitOffsets.map((offset) => ({
        guiding: offset.enabled ? "ENABLED" : "DISABLED",
        offset: {
          p: { arcseconds: offset.p },
          q: { arcseconds: offset.q }
        }
      }));
    }

    if (values.skyOffsets === Lookups.gmosImagingOffsets.UNIFORM) {
      values.skyUniformCornerAP = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-skyUniformCornerAP`,
        )?.value ?? "",
      );
      values.skyUniformCornerAQ = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-skyUniformCornerAQ`,
        )?.value ?? "",
      );
      values.skyUniformCornerBP = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-skyUniformCornerBP`,
        )?.value ?? "",
      );
      values.skyUniformCornerBQ = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-skyUniformCornerBQ`,
        )?.value ?? "",
      );
    }

    if (values.skyOffsets === Lookups.gmosImagingOffsets.SPIRAL) {
      values.skySpiralSize = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-sky-spiral-size`,
        )?.value ?? "",
      );
      values.skySpiralCenterP = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-sky-spiral-center-p`,
        )?.value ?? "",
      );
      values.skySpiralCenterQ = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-sky-spiral-center-q`,
        )?.value ?? "",
      );
    }

    if (values.skyOffsets === Lookups.gmosImagingOffsets.RANDOM) {
      values.skyRandomSize = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-sky-random-size`,
        )?.value ?? "",
      );
      values.skyRandomCenterP = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-sky-random-center-p`,
        )?.value ?? "",
      );
      values.skyRandomCenterQ = parseFloatSafe(
        this.#container.querySelector(
          `#${this.#idPrefix}-sky-random-center-q`,
        )?.value ?? "",
      );
    }

    if (variant === Lookups.gmosImagingOffsetVariant.GROUPED) {
      values.wavelengthOrder =
        this.#container.querySelector(
          `#${this.#idPrefix}-wavelength-order`,
        )?.value ?? null;
    }

    return values;
  }

  /**
   * Create an element using the local helper.
   *
   * @private
   * @param {string} tag
   * @param {string[]} [classes]
   * @returns {HTMLElement}
   */
  #createElement(tag, classes = []) {
    return Utils.createElement(tag, classes);
  }

  /**
   * Create a text element.
   *
   * @private
   * @param {string} tag
   * @param {string} text
   * @param {string[]} [classes]
   * @returns {HTMLElement}
   */
  #buildText(tag, text, classes = []) {
    const element = this.#createElement(tag, classes);
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
    const button = this.#createElement("button", classes);
    button.type = "button";
    button.innerHTML = html;
    button.addEventListener("click", onClick);
    return button;
  }
}
