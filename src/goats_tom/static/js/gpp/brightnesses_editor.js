/**
 * Class representing a dynamic UI for editing brightnesses entries.
 */
class BrightnessesEditor {
  #container;
  #table;
  #bands;
  #units;
  #idCounter = 0;

  /**
   * Construct a brightnesses editor UI.
   * @param {HTMLElement} parentElement - The parent element to render into.
   * @param {Object=} options - Optional configuration.
   * @param {string[]} [options.bands] - List of passbands.
   * @param {string[]} [options.units] - List of units.
   */
  constructor(parentElement, options = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("BrightnessEditor expects an HTMLElement as the parent.");
    }

    this.#container = Utils.createElement("div", "mb-3");

    this.#bands = options.bands ?? ["test1", "test2"];
    this.#units = options.units ?? ["test3", "test4"];

    this.#table = Utils.createElement("div", ["row", "g-3"]);

    const addButton = Utils.createElement("button", ["btn", "btn-outline-primary", "mt-3"]);
    addButton.type = "button";
    addButton.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;
    addButton.addEventListener("click", () => {
      this.#table.appendChild(this.#createInputGroup());
    });

    this.#container.append(this.#table, addButton);
    parentElement.appendChild(this.#container);
  }

  /**
   * Create and return a new input group.
   * @returns {HTMLElement} The created input group.
   * @private
   */
  #createInputGroup() {
    const col = Utils.createElement("div", "col-12");
    col.dataset.role = "brightness-col";

    const inputGroup = Utils.createElement("div", "input-group");

    const uniqueId = `brightness-${this.#idCounter++}`;

    const bandSelect = this.#createSelect(
      `${uniqueId}-band`,
      "brightnessBand",
      this.#bands
    );
    const valueInput = Utils.createElement("input", "form-control");
    valueInput.type = "number";
    valueInput.step = "any";
    valueInput.name = "brightnessValue";
    valueInput.id = `${uniqueId}-value`;

    const unitSelect = this.#createSelect(
      `${uniqueId}-units`,
      "brightnessUnits",
      this.#units
    );

    const removeBtn = Utils.createElement("button", ["btn", "btn-danger"]);
    removeBtn.type = "button";
    removeBtn.innerHTML = `<i class="fa-solid fa-minus"></i>`;
    removeBtn.title = "Remove";
    removeBtn.addEventListener("click", () => col.remove());

    inputGroup.append(bandSelect, valueInput, unitSelect, removeBtn);
    col.appendChild(inputGroup);

    return col;
  }

  /**
   * Create a <select> element with options.
   * @param {string} id - The element ID to assign.
   * @param {string} name - The name attribute of the select.
   * @param {string[]} options - Array of option values.
   * @returns {HTMLSelectElement} The configured select element.
   * @private
   */
  #createSelect(id, name, options) {
    const select = Utils.createElement("select", "form-select");
    select.name = name;
    select.id = id;

    options.forEach((option) => {
      const opt = Utils.createElement("option");
      opt.value = option;
      opt.textContent = option;
      select.appendChild(opt);
    });

    return select;
  }

  /**
   * Get values from the form, skipping entries with no value input.
   * @returns {Array<{band: string, units: string, value: number}>}
   */
  getValues() {
    const cols = this.#table.querySelectorAll('[data-role="brightness-col"]');

    return (
      Array.from(cols)
        .map((col) => {
          const band = col.querySelector('select[name="brightnessBand"]')?.value ?? "";
          const units =
            col.querySelector('select[name="brightnessUnits"]')?.value ?? "";
          const valueStr =
            col.querySelector('input[name="brightnessValue"]')?.value ?? "";
          const value = parseFloat(valueStr);

          return { band, units, value };
        })
        // Filter out any unfinished entries.
        .filter(({ value }) => !Number.isNaN(value))
    );
  }
}
