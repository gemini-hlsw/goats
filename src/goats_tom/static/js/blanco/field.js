/**
 * Turns a field description from the API into a Bootstrap 5 control.
 *
 * Every control keeps the name the Django form expects, so whatever is
 * collected can be posted straight back for the form to validate.
 */
class BlancoField {
  /**
   * Build a labelled control inside its own grid column.
   *
   * @param {Object} description Field description served by the API.
   * @returns {HTMLElement} The column, ready to append to a row.
   */
  static build(description) {
    const column = document.createElement("div");
    // Half a row or all of it: the form has no other width.
    column.className = description.width === 12 ? "col-12" : "col-md-6";
    column.dataset.field = description.name;

    const control = BlancoField.#control(description);
    const input = control.querySelector("input, select, textarea") ?? control;
    input.id = `id_${description.name}`;
    input.name = description.name;
    if (description.initial !== null && description.initial !== "") {
      BlancoField.write(input, description.initial);
    }
    if (description.required) {
      // Colour is not something a screen reader can read out.
      input.setAttribute("aria-required", "true");
      BlancoField.#askForIt(input);
    }

    const label =
      description.type === "boolean"
        ? control.querySelector(".form-check-label")
        : BlancoField.#label(description, input.id);
    // Help never takes room in the form: it lives in its button alone.
    const help = (description.help_text ?? "").trim();
    if (help) {
      label.append(BlancoField.#helpButton(help, description.label));
    }

    if (description.type !== "boolean") {
      column.append(label);
    }
    column.append(control, BlancoField.#errorSlot(description.name));
    return column;
  }

  /**
   * @private
   * @param {Object} description
   * @param {string} inputId
   * @returns {HTMLElement}
   */
  static #label(description, inputId) {
    const label = document.createElement("label");
    label.className = "form-label mb-1";
    label.htmlFor = inputId;
    label.textContent = description.label;
    if (description.required) {
      label.title = "Required";
    }
    return label;
  }

  /**
   * Colour a required control until it is answered.
   *
   * What is asked for is asked for on the control itself, and only while it
   * is empty: once it holds something it has nothing left to say.
   *
   * @private
   * @param {HTMLElement} input
   * @returns {void}
   */
  static #askForIt(input) {
    ["input", "change", "blur"].forEach((event) =>
      input.addEventListener(event, () => BlancoField.recheck(input)),
    );
    BlancoField.recheck(input);
  }

  /**
   * Look again at whether a required control is still empty.
   *
   * A value can be put in without anybody typing it -- narrowing a select to
   * what an instrument takes does exactly that -- and no event is raised for
   * it, so whoever writes the value says when to look.
   *
   * @param {HTMLElement} input
   * @returns {void}
   */
  static recheck(input) {
    if (input.getAttribute("aria-required") !== "true") {
      return;
    }
    const empty = !String(input.value ?? "").trim();
    input.classList.toggle("border-danger", empty);
  }

  /**
   * The button a field's help hides behind.
   *
   * Some of the toolkit's help is written as markup, and what it links to is
   * the best of it -- the visibility calculator, the facility's own pages.
   * A tooltip would flatten that to words nobody can follow, so the help
   * opens in a popover, which keeps the link and lets it be clicked.
   *
   * @private
   * @param {string} help
   * @param {string} label The field it belongs to.
   * @returns {HTMLElement}
   */
  static #helpButton(help, label) {
    const words = document.createElement("div");
    words.innerHTML = help;
    // Whatever the toolkit wrote, a link out of GOATS opens beside it.
    words.querySelectorAll("a").forEach((link) => {
      link.target = "_blank";
      link.rel = "noopener";
    });

    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-link p-0 ms-1 align-baseline text-decoration-none";
    button.dataset.role = "help";
    button.setAttribute("aria-label", `Help for ${label}`);
    // GOATS ships the solid and brands sets only; fa-regular draws nothing.
    button.innerHTML = '<i class="fa-solid fa-circle-question"></i>';
    // The label would hand the click on to the control it names.
    button.addEventListener("click", (event) => event.preventDefault());

    if (typeof bootstrap !== "undefined" && bootstrap.Popover) {
      new bootstrap.Popover(button, {
        html: true,
        content: words.innerHTML,
        trigger: "click",
        placement: "top",
      });
      BlancoField.#dismissOnOutsideClick();
    } else {
      // Nothing to open a popover with: the words alone, as a tooltip.
      button.title = words.textContent.replace(/\s+/g, " ").trim();
    }
    return button;
  }

  /** Whether a click anywhere else is already being watched for. */
  static #watching = false;

  /**
   * Close an open help when the reader looks elsewhere.
   *
   * A popover opened by a click stays until it is clicked again, which
   * leaves it standing over the form. One listener closes them all, so the
   * form does not gain one per field it explains.
   *
   * @private
   * @returns {void}
   */
  static #dismissOnOutsideClick() {
    if (BlancoField.#watching) {
      return;
    }
    BlancoField.#watching = true;
    document.addEventListener("click", (event) => {
      if (event.target.closest('[data-role="help"], .popover')) {
        return;
      }
      document
        .querySelectorAll('[data-role="help"]')
        .forEach((button) => bootstrap.Popover.getInstance(button)?.hide());
    });
  }

  /**
   * @private
   * @param {string} name
   * @returns {HTMLElement}
   */
  static #errorSlot(name) {
    const slot = document.createElement("div");
    slot.className = "invalid-feedback d-block d-none";
    slot.dataset.errorFor = name;
    return slot;
  }

  /**
   * @private
   * @param {Object} description
   * @returns {HTMLElement} The control, or a wrapper holding it.
   */
  static #control(description) {
    if (description.type === "choice") {
      const select = document.createElement("select");
      select.className = "form-select";
      (description.choices ?? []).forEach(({ value, label }) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        select.append(option);
      });
      return select;
    }

    if (description.type === "boolean") {
      const check = document.createElement("div");
      check.className = "form-check";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.className = "form-check-input";
      const label = document.createElement("label");
      label.className = "form-check-label";
      label.textContent = description.label;
      label.htmlFor = `id_${description.name}`;
      check.append(input, label);
      return check;
    }

    const input = document.createElement("input");
    input.className = "form-control";
    input.type = BlancoField.#inputType(description.type);
    if (description.type === "float") {
      input.step = "any";
    }
    if (description.placeholder) {
      input.placeholder = description.placeholder;
    }
    ["min", "max"].forEach((bound) => {
      if (description[bound] !== undefined) {
        input.setAttribute(bound, description[bound]);
      }
    });
    return description.unit ? BlancoField.#measured(input, description.unit) : input;
  }

  /**
   * Put what a control is measured in beside it, as the GPP form does.
   *
   * @private
   * @param {HTMLElement} input
   * @param {string} unit
   * @returns {HTMLElement}
   */
  static #measured(input, unit) {
    const group = document.createElement("div");
    group.className = "input-group";
    const measure = document.createElement("span");
    measure.className = "input-group-text";
    measure.dataset.role = "unit";
    measure.textContent = unit;
    group.append(input, measure);
    return group;
  }

  /**
   * @private
   * @param {string} type
   * @returns {string}
   */
  static #inputType(type) {
    if (type === "integer" || type === "float") {
      return "number";
    }
    if (type === "datetime") {
      return "datetime-local";
    }
    return "text";
  }

  /**
   * Put a value into a control.
   *
   * @param {HTMLElement} input
   * @param {*} value
   * @returns {void}
   */
  static write(input, value) {
    if (input.type === "checkbox") {
      input.checked = Boolean(value);
      return;
    }
    input.value = value;
  }

  /**
   * Read a control, in the shape the Django form expects.
   *
   * A split datetime is two values, so it comes back as an object of the
   * `_0` (date) and `_1` (time) halves the form is built from.
   *
   * @param {HTMLElement} input
   * @returns {Object} Field names mapped to their values.
   */
  static read(input) {
    if (input.type === "checkbox") {
      return { [input.name]: input.checked };
    }
    if (input.type === "datetime-local") {
      const [date = "", time = ""] = String(input.value).split("T");
      return { [`${input.name}_0`]: date, [`${input.name}_1`]: time };
    }
    return { [input.name]: input.value };
  }
}

if (typeof module !== "undefined") {
  module.exports = { BlancoField };
}
