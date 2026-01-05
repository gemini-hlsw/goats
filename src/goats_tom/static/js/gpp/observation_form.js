/**
 * Class representing the observation form UI.
 */
class ObservationForm {
  #container;
  #form;
  #handlers;
  #readOnly;
  #mode;
  #schedulingWindowsEditor;

  /**
   * Create an ObservationForm.
   * @param {HTMLElement} parentElement - The container to render the form into.
   * @param {Object} [options] - Optional configuration.
   * @param {Object=} options.observation - Initial observation data.
   * @param {"normal"|"too"} [options.mode="normal"] - Observation mode.
   * @param {boolean} [options.readOnly=false] - If true, disables all inputs.
   */
  constructor(
    parentElement,
    { observation = null, mode = "normal", readOnly = false } = {}
  ) {
    this.#container = parentElement;
    this.#form = null;
    this.#readOnly = readOnly;
    this.#mode = mode;

    // Register special handlers like brightness, sourceProfile etc.
    this.#handlers = {
      handlePosAngleConstraint: (meta, raw) => {
        // Need to wrap to preserve layout and match rest.
        const wrapper = Utils.createElement("div", "mt-3");
        const div = Utils.createElement("div", ["row", "g-3"]);
        // Mode dropdown.
        const modeField = this.#createFormField({
          id: `${meta.id}Mode`,
          labelText: "Position Angle Mode",
          element: meta.element,
          options: meta.options,
          value: raw?.mode ?? meta.value,
        });

        // Show angle input only for certain modes.
        const showAngle = ["ALLOW_180_FLIP", "PARALLACTIC_OVERRIDE", "FIXED"].includes(
          raw?.mode
        );

        const angleField = this.#createFormField({
          id: `${meta.id}Angle`,
          labelText: "\u00A0", // Non-breaking space to align.
          type: "number",
          suffix: meta.suffix,
          value: raw?.angle?.degrees ?? "",
          colSize: "col-md-6",
        });

        if (!showAngle) angleField.classList.add("d-none");

        // Add event listener to toggle angle field.
        modeField.querySelector("select")?.addEventListener("change", (e) => {
          const selected = e.target.value;
          const showAngle = [
            "ALLOW_180_FLIP",
            "PARALLACTIC_OVERRIDE",
            "FIXED",
          ].includes(selected);
          angleField.classList.toggle("d-none", !showAngle);
        });

        div.append(modeField, angleField);
        wrapper.appendChild(div);
        return [wrapper];
      },
      handleExposureMode: (meta, raw) => {
        const div = Utils.createElement("div", "mt-3");
        new ExposureModeEditor(div, {
          data: raw ?? {},
          readOnly: this.#readOnly,
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

    this.#form.querySelectorAll("input,select,textarea,button").forEach((el) => {
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
         const { header, body } = this.#createSectionWithBody(meta.section, form);
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
           handler(meta, raw).forEach((el) => currentSectionBody.append(el));
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
     const normalizedSection = text.toLowerCase().replace(/\s+/g, "-")
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
   
     const toggleBtn = Utils.createElement("button", [
       "btn",
       "p-0",
     ]);
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
     body.setAttribute("data-bs-parent", "#profile-accordion");
   
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
    options = [],
  }) {
    const elementId = `${id}${Utils.capitalizeFirstLetter(element)}`;

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

    // Create label.
    if (labelText) {
      const label = Utils.createElement("label", ["form-label"]);
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
        // Handle if option passed in is just a list of strings.
        if (typeof opt === "string") {
          optionEl.value = opt;
          optionEl.textContent = opt;
        } else {
          // User passed in JSON object {value: "", labelText: ""}.
          optionEl.value = opt.value;
          optionEl.textContent = opt.labelText;

          // Handle disabled state.
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
    // Apply read-only state if applicable.
    // Use the global readOnly flag.
    // Otherwise, if readOnly is "both" or matches current mode, disable the control.
    const isReadOnly =
      this.#readOnly ||
      (typeof readOnly === "string" &&
        (readOnly === "both" || readOnly === this.#mode));
    control.disabled = isReadOnly;

    // Wrap and append.
    col.append(this.#wrapWithGroup(control, { prefix, suffix }));
    return col;
  }

  /**
   * Wrap form control in input group for prefix/suffix.
   * @param {HTMLElement} control - Form control.
   * @param {Object} options
   * @param {string=} options.prefix - Prefix text.
   * @param {string=} options.suffix - Suffix text.
   * @returns {HTMLElement}
   * @private
   */
  #wrapWithGroup(control, { prefix, suffix }) {
    if (!prefix && !suffix) return control;

    const group = Utils.createElement("div", ["input-group"]);
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
        `Unsupported observing mode: "${mode}". No instrument-specific fields will be rendered.`
      );
    }

    return [...sharedFields, ...instrumentFields];
  }

  /**
   * Get the current form data as FormData.
   * @returns {FormData|null} FormData object or null if form not initialized.
   */
  getData() {
    if (!this.#form) return null;
    const formData = new FormData(this.#form);
    const timingWindows = this.#schedulingWindowsEditor.getValues();
    formData.append("timingWindows", JSON.stringify(timingWindows))
    return formData;
  }
}
