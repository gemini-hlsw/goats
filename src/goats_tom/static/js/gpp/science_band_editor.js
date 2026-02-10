/**
 * Convert "BAND1" -> "BAND-1" for display purposes.
 *
 * @param {string} band
 * @returns {string}
 */
function normalizeBandLabel(band) {
  return String(band ?? "").trim().replace(/^BAND(\d+)$/, "BAND-$1");
}

/**
 * ScienceBandEditor
 *
 * Renders a Bootstrap-styled dropdown that behaves like a single-select.
 * The menu shows "BAND-x" on the left and remaining time on the right.
 *
 * Expected input shape:
 *   data = [bandSelected, bandOptions, timeCharge]
 */
class ScienceBandEditor {
  /** @type {HTMLElement} */
  #parentElement;

  /** @type {string} */
  #bandSelected;

  /** @type {Array} */
  #bandOptions;

  /** @type {*} */
  #timeCharge;

  /**
   * @param {HTMLElement} parentElement
   * @param {{ data?: [string, Array, any] }} [options]
   */
  constructor(parentElement, { data = [] } = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("ScienceBandEditor expects an HTMLElement as the parent.");
    }

    const [bandSelected = "", bandOptions = [], timeCharge = null] = data;

    this.#parentElement = parentElement;
    this.#bandSelected = String(bandSelected ?? "").trim();
    this.#bandOptions = Array.isArray(bandOptions) ? bandOptions : [];
    this.#timeCharge = timeCharge;

    this.#render();
  }

  /**
   * Compute remaining hours for a given band entry.
   *
   * @param {Object} band
   * @param {number} programTime
   * @returns {number}
   */
  #remainingFor(band, programTime) {
    const duration = Number(band?.duration?.hours ?? band?.duration ?? 0);
    return Math.max(0, duration - programTime);
  }

  /**
   * Build the UI and wire events.
   */
  #render() {
    const fieldId = "scienceBand";

    // Label
    const label = Utils.createElement("label", "form-label");
    label.textContent = "Science Band";
    label.setAttribute("for", fieldId);
    this.#parentElement.appendChild(label);

    // No options
    if (this.#bandOptions.length === 0) {
      const disabled = Utils.createElement("div", "form-select");
      disabled.classList.add("text-muted");
      disabled.textContent = "No bands available";
      this.#parentElement.appendChild(disabled);
      return;
    }

    const programTime = Number(this.#timeCharge?.band?.time?.program ?? 0);

    // Wrapper
    const wrapper = Utils.createElement("div");
    wrapper.classList.add("dropdown");
    this.#parentElement.appendChild(wrapper);

    // Button (select-like)
    const button = Utils.createElement("button", "form-select");
    button.type = "button";
    button.classList.add("text-start");
    button.setAttribute("data-bs-toggle", "dropdown");
    button.setAttribute("aria-expanded", "false");
    wrapper.appendChild(button);

    // Hidden native select (source of truth)
    const select = Utils.createElement("select");
    select.id = fieldId;
    select.classList.add("d-none");
    wrapper.appendChild(select);

    // Dropdown menu
    const menu = Utils.createElement("div");
    menu.classList.add("dropdown-menu", "w-100", "p-1");
    wrapper.appendChild(menu);

    /** @type {Map<string, string>} */
    const labelByValue = new Map();

    // Empty option + empty menu row (same height as other items)
    select.appendChild(new Option("", ""));
    const emptyItem = Utils.createElement("button");
    emptyItem.type = "button";
    emptyItem.dataset.value = "";
    emptyItem.classList.add("dropdown-item");
    emptyItem.textContent = "\u00A0";
    menu.appendChild(emptyItem);

    // Band options
    for (const band of this.#bandOptions) {
      const value = String(band?.scienceBand ?? "").trim();
      if (!value) continue;

      const bandLabel = normalizeBandLabel(value);
      labelByValue.set(value, bandLabel);

      // Native option
      select.appendChild(new Option(bandLabel, value));

      // Menu item (two columns)
      const item = Utils.createElement("button");
      item.type = "button";
      item.dataset.value = value;
      item.classList.add(
        "ps-2",
        "dropdown-item",
        "d-flex",
        "justify-content-between",
        "align-items-center"
      );

      const left = Utils.createElement("span");
      left.textContent = bandLabel;

      const right = Utils.createElement("span");
      right.classList.add("text-muted");
      right.style.fontWeight = "500";
      right.textContent = `${this.#remainingFor(band, programTime)} hr remaining`;

      item.appendChild(left);
      item.appendChild(right);
      menu.appendChild(item);
    }

    // Initial value (can be empty)
    select.name = "scienceBand"; 
    select.value = labelByValue.has(this.#bandSelected) ? this.#bandSelected : "";
    this.#bandSelected = select.value;

    const sync = () => {
      button.textContent = labelByValue.get(select.value) ?? "\u00A0";
    };

    // Menu click -> update select + fire change
    menu.addEventListener("click", (e) => {
      const item = e.target.closest("[data-value]");
      if (!item) return;

      select.value = item.dataset.value;
      this.#bandSelected = select.value;

      sync();
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });

    // External changes safety
    select.addEventListener("change", () => {
      this.#bandSelected = select.value;
      sync();
    });

    sync();
  }
  getValues() {
    return this.#bandSelected;
  }
}

