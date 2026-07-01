/**
 * Class representing the observation form UI.
 */
class ObservationForm {
  #container;
  #form;
  #handlers;
  #readOnly;
  #allowStateEdit;
  #mode;
  #callbacks;
  #target;
  #schedulingWindowsEditor;
  #finderChartEditor;

  /**
   * Create an ObservationForm.
   * @param {HTMLElement} parentElement - The container to render the form into.
   * @param {Object} [options] - Optional configuration.
   * @param {Object=} options.observation - Initial observation data.
   * @param {"normal"|"too"} [options.mode="normal"] - Observation mode.
   * @param {boolean} [options.readOnly=false] - If true, disables all inputs.
   * @param {boolean} [options.allowStateEdit=false] - If true, keeps the State
   *   field editable even when the form is read-only.
   * @param {Object=} options.target - Selected target info ({name, ra, dec}) used
   *   by override fields to display the target's value when locked.
   */
  constructor(
    parentElement,
    {
      observation = null,
      mode = "normal",
      readOnly = false,
      allowStateEdit = false,
      target = null,
      callbacks = {},
    } = {},
  ) {
    this.#container = parentElement;
    this.#form = null;
    this.#readOnly = readOnly;
    this.#allowStateEdit = allowStateEdit;
    //this.#readOnly = true;
    this.#mode = mode;
    this.#target = target ?? {};
    this.#callbacks = callbacks ?? {};

    // Register special handlers like brightness, sourceProfile etc.
    this.#handlers = {
      handlePosAngleConstraint: (meta, raw) => {
        // Need to wrap to preserve layout and match rest.
        const div = Utils.createElement("div", "mt-3");
        new PosAngleEditor(div, {
          data: raw ?? {},
          meta: meta ?? {},
          readOnly: this.#readOnly,
        });
        return [div];
      },
      handleExposureMode: (meta, raw) => {
        const div = Utils.createElement("div", "mt-3");
        new ExposureModeEditor(div, {
          data: raw ?? {},
          mode: meta.mode,
          readOnly: this.#readOnly || meta.readOnly,
        });
        return [div];
      },
      handleElevationRange: (meta, raw) => {
        const div = Utils.createElement("div", "mt-3");
        new ElevationRangeEditor(div, {
          data: raw ?? {},
          readOnly: this.#readOnly,
        });
        return [div];
      },
      handleSourceProfile: (meta, raw) => {
        const div = Utils.createElement("div", "mt-3");
        new SourceProfileEditor(div, {
          data: raw ?? {},
          debug: true,
          readOnly: this.#readOnly,
        });
        return [div];
      },
      handleBrightnessInputs: (meta, raw) => {
        const div = Utils.createElement("div", "mt-3");
        new BrightnessesEditor(div, {
          data: raw ?? [],
          readOnly: this.#readOnly,
        });
        return [div];
      },
      handleSchedulingWindowsInputs: (meta, raw) => {
        const div = Utils.createElement("div", "mt-3");
        this.#schedulingWindowsEditor = new SchedulingWindowsEditor(div, {
          data: raw ?? [],
          readOnly: this.#readOnly,
        });
        return [div];
      },
      handleSpatialOffsetsList: (meta, raw) => {
        const values = raw?.map((o) => o.arcseconds.toFixed(2)) ?? [];
        return [this.#createFormField({ ...meta, value: values.join(", ") })];
      },
      handleWavelengthDithersList: (meta, raw) => {
        const values = raw?.map((o) => o.nanometers.toFixed(1)) ?? [];
        return [this.#createFormField({ ...meta, value: values.join(", ") })];
      },
      handleScienceBand: (meta, raw) => {
        const div = Utils.createElement("div", "col-lg-6");
        if (!observation) return [div];
        const allocations = Utils.getByPath(observation, meta.allocationsPath);
        const timeCharge = Utils.getByPath(observation, meta.timeChargePath);
        new ScienceBandEditor(div, {
          data: [raw ?? null, allocations, timeCharge],
          readOnly: this.#readOnly,
        });
        return [div];
      },
      handleFinderCharts: (meta, raw) => {
        const div = Utils.createElement("div", "mt-0");
        this.#finderChartEditor = new FinderChartEditor(div, {
          data: raw ?? [],
          callbacks: this.#callbacks,
          readOnly: this.#readOnly,
        });
        return [div];
      },
      handleOffsetVariant: (meta, raw) => {
        const div = Utils.createElement("div", "mt-3");
        new OffsetVariantEditor(div, {
          data: raw ?? [],
          readOnly: this.#readOnly,
        });
        return [div];
      },
    };

    if (observation) {
      this.load(observation);
    }
  }

  /**
   * Load and render form with observation data.
   * @param {Object} observation - Observation data to populate.
   */
  load(observation) {
    this.clear();

    const form = Utils.createElement("form", ["row", "g-3"]);
    this.#form = form;

    const allFields = this.#getMergedFields(observation);
    this.#appendFields(form, allFields, observation);

    this.#container.appendChild(form);
  }

  /**
   * Clear the form UI.
   */
  clear() {
    this.#container.innerHTML = "";
    this.#form = null;
  }

  /**
   * Toggle read-only state for all form fields.
   * @param {boolean} flag - Whether the form should be read-only.
   */
  toggleReadOnly(flag) {
    this.#readOnly = flag;
    if (!this.#form) return;

    this.#form
      .querySelectorAll("input,select,textarea,button")
      .forEach((el) => {
        if (el.tagName === "BUTTON") {
          el.classList.toggle("d-none", flag);
        } else {
          el.disabled = flag;
        }
      });
  }

  /**
   * Append rendered fields to the form.
   * @param {HTMLElement} form - The form container.
   * @param {Array<Object>} fields - Field metadata.
   * @param {Object} observation - The current observation data.
   * @private
   */
  #appendFields(form, fields, observation) {
    // By default, fields are appended directly to the form.
    // Once we hit a `meta.section`, we switch to that section's body.
    form.id = "profile-accordion";
    let currentSectionBody = form;

    fields.forEach((meta) => {
      // Skip field if showIfMode is incompatible with current mode.
      if (
        meta.showIfMode &&
        meta.showIfMode !== "both" &&
        meta.showIfMode !== this.#mode
      ) {
        return;
      }

      // Handle section headers: create header + collapsible body.
      if (meta.section) {
        const { header, body } = this.#createSectionWithBody(
          meta.section,
          form,
        );
        form.append(header);
        form.append(body);

        // From now on, append all fields into this section body
        currentSectionBody = body;
        return;
      }

      const raw = Utils.getByPath(observation, meta.path);

      // Handle special field handlers.
      if (meta.handler) {
        const handler = this.#handlers[meta.handler];
        if (handler) {
          const elements = handler(meta, raw) ?? [];
          elements.forEach((el) => currentSectionBody.append(el));
        }
        return;
      }

      let value = raw;
      // Assign raw value from lookup or format if applicable.
      if (meta.lookup) value = meta.lookup[raw] ?? raw ?? "";
      if (meta.formatter) value = meta.formatter(value);

      currentSectionBody.append(this.#createFormField({ ...meta, value }));
    });
  }
  /**
   * Create a section header with a collapse toggle and a body container.
   *
   * The header is a flex row with the title on the left and a collapse icon on the right.
   * The body is a <div class="collapse [show] mt-2"> that will contain all the fields
   * belonging to this section.
   *
   * @param {string} text - Section title.
   * @returns {{ header: HTMLElement, body: HTMLElement }}
   * @private
   */
  #createSectionWithBody(text, form) {
    // Build a stable id from the section text
    const normalizedSection = text.toLowerCase().replace(/\s+/g, "-");
    const collapseId = `section-${normalizedSection}`;

    const header = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "justify-content-between",
      "mt-4",
      "mb-0",
    ]);

    const h = Utils.createElement("h5", ["mb-0"]);
    h.textContent = text;

    const toggleBtn = Utils.createElement("button", ["btn", "p-0"]);
    toggleBtn.type = "button";
    toggleBtn.setAttribute("data-bs-toggle", "collapse");
    toggleBtn.setAttribute("data-bs-target", `#${collapseId}`);
    toggleBtn.setAttribute("aria-controls", collapseId);

    const bodyClasses = Array.from(form.classList);
    bodyClasses.push("collapse");

    if (text === "Details") {
      bodyClasses.push("show");
    }

    const body = Utils.createElement("div", bodyClasses);
    body.id = collapseId;

    const setExpandedState = (expanded) => {
      toggleBtn.setAttribute("aria-expanded", String(expanded));
      toggleBtn.innerHTML = expanded
        ? `<i class="fa-solid fa-chevron-up"></i>`
        : `<i class="fa-solid fa-chevron-down"></i>`;
    };

    const initiallyExpanded = body.classList.contains("show");
    setExpandedState(initiallyExpanded);

    body.addEventListener("show.bs.collapse", () => {
      setExpandedState(true);
    });

    body.addEventListener("hide.bs.collapse", () => {
      setExpandedState(false);
    });

    header.append(h, toggleBtn);
    header.addEventListener("click", (event) => {
      if (event.target === toggleBtn || toggleBtn.contains(event.target)) {
        return;
      }
      toggleBtn.click();
    });

    return { header, body };
  }
  /**
   * Create a form field from metadata.
   * @param {Object} field - Field configuration metadata.
   * @param {string} field.id - Field ID.
   * @param {*} field.value - Initial field value.
   * @param {string=} field.labelText - Field label.
   * @param {string=} field.prefix - Optional prefix text.
   * @param {string=} field.suffix - Optional suffix text.
   * @param {string=} field.element - Element type: input, textarea, or select.
   * @param {string=} field.type - Input type (e.g., "number", "text").
   * @param {string=} field.colSize - Bootstrap column class.
   * @param {string=} field.readOnly - Whether the field is read-only in what mode.
   * @param {boolean=} field.hasOverride - If true, field has a "target" (bullseye)
   *     button inside the input group. When active (locked), the field shows the
   *     selected target's value but stays disabled, so it is not submitted and the
   *     serializer falls back to the target value. When inactive, the value is
   *     editable and the custom value is submitted.
   * @param {string=} field.overridePlaceholder - Placeholder shown when field is locked.
   *     E.g. "Using selected target's RA".
   * @param {string=} field.lockOverrideInMode - Mode ("normal", "too", or "both") in which
   *     the override starts locked (using the target's value). The toggle still lets the
   *     user unlock to edit and lock again.
   * @param {string=} field.targetValueKey - Key into the form's target info
   *     ({name, ra, dec}) whose value is displayed while the override is locked.
   * @param {Array<string|{labelText: string, value: string}>=} field.options - Options for a
   * select element.
   * @returns {!HTMLElement}
   * @private
   */
  #createFormField({
    id,
    value = "",
    labelText = null,
    prefix = null,
    suffix = null,
    element = "input",
    type = "text",
    colSize = "col-md-6",
    readOnly = undefined,
    hasOverride = false,
    overridePlaceholder = "Using selected target's value",
    lockOverrideInMode = undefined,
    targetValueKey = undefined,
    options = [],
  }) {
    const elementId = `${id}${Utils.capitalizeFirstLetter(element)}`;

    // The selected target's value shown while the override is locked.
    const targetValue = targetValueKey
      ? (this.#target?.[targetValueKey] ?? "")
      : "";

    // Handle creating a hidden input and return early to avoid breaking layout.
    if (type === "hidden") {
      const input = Utils.createElement("input");
      input.type = type;
      input.id = elementId;
      input.name = elementId;
      input.value = value;
      return input;
    }

    const col = Utils.createElement("div", [colSize]);

    // Apply read-only state if applicable.
    const isReadOnly =
      (this.#readOnly && !(this.#allowStateEdit && labelText === "State")) ||
      (typeof readOnly === "string" &&
        (readOnly === "both" || readOnly === this.#mode));

    // Whether the override should start locked (using the target's value) for the
    // current mode. The toggle still lets the user unlock and re-lock afterwards.
    const startLocked =
      hasOverride &&
      !isReadOnly &&
      typeof lockOverrideInMode === "string" &&
      (lockOverrideInMode === "both" || lockOverrideInMode === this.#mode);

    // Create label (the override toggle lives inside the input group instead).
    if (labelText) {
      const label = Utils.createElement("label", ["form-label", "mb-1"]);
      label.htmlFor = elementId;
      label.textContent = labelText;
      col.append(label);
    }

    // Create form control.
    let control;
    if (element === "textarea") {
      control = Utils.createElement("textarea", ["form-control"]);
      control.rows = 3;
      control.value = value;
    } else if (element === "input") {
      control = Utils.createElement("input", ["form-control"]);
      control.type = type;
      if (control.type === "number") {
        control.step = "any"; // Allow decimals.
      }
      control.value = value;
    } else if (element === "select") {
      control = Utils.createElement("select", ["form-select"]);
      options.forEach((opt) => {
        const optionEl = Utils.createElement("option");
        if (typeof opt === "string") {
          optionEl.value = opt;
          optionEl.textContent = opt;
        } else {
          optionEl.value = opt.value;
          optionEl.textContent = opt.labelText;
          if (opt.disabled) {
            optionEl.disabled = true;
          }
        }
        if (optionEl.value === value) {
          optionEl.selected = true;
        }
        control.appendChild(optionEl);
      });
    } else {
      console.error("Unsupported element:", element);
      return col;
    }

    control.id = elementId;
    control.name = elementId;
    control.disabled = isReadOnly;

    // Override toggle: a "target" (bullseye) button inside the input group that
    // switches the field between the selected target's value and a custom value.
    let overrideButton = null;
    if (hasOverride && !isReadOnly) {
      overrideButton = this.#createOverrideToggle(control, {
        elementId,
        targetValue,
        value,
        overridePlaceholder,
        startLocked,
      });
    }

    // Wrap and append.
    col.append(
      this.#wrapWithGroup(control, { prefix, suffix, overrideButton }),
    );
    return col;
  }

  /**
   * Create the "target" (bullseye) override toggle for a field.
   *
   * The returned button is rendered as the leading input-group addon. When active
   * (locked) the control shows the selected target's value but stays disabled, so
   * it is not submitted and the serializer falls back to the target value; when
   * inactive the control is editable with a custom value.
   *
   * @param {HTMLElement} control - The field's input/textarea control.
   * @param {Object} options
   * @param {string} options.elementId - The control's DOM id (used for the button id).
   * @param {string} options.targetValue - The selected target's value shown when locked.
   * @param {string} options.value - The custom value restored when unlocked.
   * @param {string} options.overridePlaceholder - Placeholder shown while locked.
   * @param {boolean} options.startLocked - Whether the toggle starts locked.
   * @returns {!HTMLElement} The toggle button.
   * @private
   */
  #createOverrideToggle(
    control,
    { elementId, targetValue, value, overridePlaceholder, startLocked },
  ) {
    // Styled as an input-group addon (not a full button); only the bullseye icon
    // changes color: primary when active, secondary when inactive.
    const button = Utils.createElement("button", ["input-group-text"]);
    button.type = "button";
    button.id = `${elementId}Toggle`;
    button.innerHTML = `<i class="fa-solid fa-location-crosshairs fa-lg"></i>`;

    // Keep the target's value legible while the field is disabled: `.text-body`
    // uses `!important`, overriding the faded `:disabled` color from the theme.

    const applyLocked = (locked) => {
      button.dataset.locked = locked ? "true" : "false";
      // FontAwesome swaps the <i> for an <svg> (fill: currentColor), so set the
      // color on the button itself and let the icon inherit it.
      button.classList.toggle("text-primary", locked);
      button.classList.toggle("text-secondary", !locked);
      if (locked) {
        // Use the target's value: show it but keep the input disabled so it is
        // not submitted and the serializer falls back to the target value.
        control.disabled = true;
        control.placeholder = overridePlaceholder;
        control.value = targetValue;
        button.title =
          "Using the target's value. Click to enter a custom value.";
      } else {
        // Use a custom value: restore the editable value.
        control.disabled = false;
        control.placeholder = "";
        control.value = value;
        button.title = "Using a custom value. Click to use the target's value.";
      }
    };

    applyLocked(startLocked);

    button.addEventListener("click", () => {
      const wasLocked = button.dataset.locked === "true";
      applyLocked(!wasLocked);
      if (wasLocked) control.focus();
    });

    return button;
  }

  /**
   * Wrap form control in input group for prefix/suffix.
   * @param {HTMLElement} control - Form control.
   * @param {Object} options
   * @param {string=} options.prefix - Prefix text.
   * @param {string=} options.suffix - Suffix text.
   * @param {HTMLElement=} options.overrideButton - Optional "target" toggle button
   *     rendered as the leading input-group addon.
   * @returns {HTMLElement}
   * @private
   */
  #wrapWithGroup(control, { prefix, suffix, overrideButton = null }) {
    if (!prefix && !suffix && !overrideButton) return control;

    const group = Utils.createElement("div", ["input-group"]);
    if (overrideButton) group.append(overrideButton);
    if (prefix) {
      const pre = Utils.createElement("span", ["input-group-text"]);
      pre.textContent = prefix;
      group.append(pre);
    }
    group.append(control);
    if (suffix) {
      const post = Utils.createElement("span", ["input-group-text"]);
      post.textContent = suffix;
      group.append(post);
    }
    return group;
  }

  /**
   * Merge shared and instrument-specific fields for an observation.
   * @param {Object} observation - The observation payload.
   * @returns {Array<Object>} Full list of field metadata entries.
   * @private
   */
  #getMergedFields(observation) {
    const sharedFields = SHARED_FIELDS;
    const mode = observation?.observingMode?.mode;
    const instrumentFields = FIELD_CONFIGS[mode] ?? [];

    if (!FIELD_CONFIGS.hasOwnProperty(mode)) {
      console.warn(
        `Unsupported observing mode: "${mode}". No instrument-specific fields will be rendered.`,
      );
    }

    return [...sharedFields, ...instrumentFields];
  }
  getData() {
    if (!this.#form) return null;

    const formData = new FormData(this.#form);

    // Calibrations are read-only except for the State field, so flag the request
    // to update only the workflow state on the backend.
    if (this.#allowStateEdit) {
      formData.append("isCalibration", "true");
    }

    // timing windows
    const timingWindows = this.#schedulingWindowsEditor.getValues();
    formData.append("timingWindows", JSON.stringify(timingWindows));

    // finder charts
    const { toAdd, toDelete } = this.#finderChartEditor.getPendingChanges();

    const finderCharts = {
      toAdd: toAdd.map((item, index) => ({
        description: item.description ?? "",
        fileKey: `file_${index}`,
      })),
      toDelete,
    };

    formData.append("finderCharts", JSON.stringify(finderCharts));

    toAdd.forEach((item, index) => {
      const key = `file_${index}`;
      formData.append(key, item.file);
    });

    return formData;
  }
}
