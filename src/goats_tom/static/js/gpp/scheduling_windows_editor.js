const MODES = Object.freeze({
  FOREVER: "Forever",
  THROUGH: "Through",
  FOR: "For",
});

const REPEAT_MODES = Object.freeze({
  FOREVER: "Forever",
  TIMES: "Times",
});
/**
 * Parse a duration string "HH", "HH:MM" or "HH:MM:SS" into seconds.
 *
 * @param {string} text
 * @returns {number}
 */
function parseDurationToSeconds(text) {
  if (!text) return 0;

  const parts = text.split(":").map(Number);
  if (parts.some((n) => Number.isNaN(n))) return 0;

  if (parts.length === 1) {
    const [hours] = parts;
    return hours * 3600;
  }

  if (parts.length === 2) {
    const [hours, minutes] = parts;
    return hours * 3600 + minutes * 60;
  }

  if (parts.length === 3) {
    const [hours, minutes, seconds] = parts;
    return hours * 3600 + minutes * 60 + seconds;
  }

  return 0;
}

/**
 * Return current UTC datetime formatted for <input type="datetime-local">.
 *
 * @returns {string} Datetime string in "YYYY-MM-DDTHH:MM"
 */
function getNowForDatetimeLocalUtc() {
  return new Date().toISOString().slice(0, 16);
}

/**
 * Format a duration in seconds into a human-readable string.
 *
 * @param {number|null|undefined} seconds - Duration in seconds.
 * @returns {string} Human-readable duration or empty string if invalid.
 */
function secondsToHumanReadableString(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "";

  const abs = Math.abs(Number(seconds));

  const days = Math.floor(abs / 86400);
  const hours = Math.floor((abs % 86400) / 3600);
  const minutes = Math.floor((abs % 3600) / 60);
  const secs = Math.floor(abs % 60);

  const parts = [];

  if (days > 0) {
    parts.push(`${days} day${days === 1 ? "" : "s"}`);
  }
  if (hours > 0) {
    parts.push(`${hours} hour${hours === 1 ? "" : "s"}`);
  }
  if (minutes > 0) {
    parts.push(`${minutes} minute${minutes === 1 ? "" : "s"}`);
  }
  if (secs > 0 && parts.length === 0) {
    parts.push(`${secs} second${secs === 1 ? "" : "s"}`);
  }

  return parts.join(", ");
}

/**
 * Editor component for managing a list of scheduling windows.
 *
 * Renders:
 *  - A list of existing windows with Include/Exclude badges.
 *  - Controls to define a new window (type, start time, mode, repeat).
 */
class SchedulingWindowsEditor {
  /** @type {HTMLElement} */
  #container;
  /** @type {HTMLElement} */
  #tableBox;
  /** @type {HTMLElement} */
  #list;
  /** @type {Array<Object>} */
  #timingWindows;
  /** @type {string} */
  #idPrefix;

  /**
   * Construct a scheduling windows editor UI.
   *
   * @param {HTMLElement} parentElement - The parent element to render into.
   * @param {{data?: Array<Object>, idPrefix?: string}} [options]
   * @param {Array<Object>} [options.data=[]] - Initial list of timing windows.
   * @param {string} [options.idPrefix="scheduling-windows"] - Prefix for element ids.
   * @throws {Error} If parentElement is not an HTMLElement.
   */
  constructor(
    parentElement,
    { data = [], idPrefix = "scheduling-windows" } = {},
  ) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error(
        "SchedulingWindowsEditor expects an HTMLElement as the parent.",
      );
    }

    this.#timingWindows = Array.isArray(data) ? [...data] : [];
    this.#idPrefix = idPrefix;

    this.#container = Utils.createElement("div", ["d-flex", "flex-column"]);
    parentElement.appendChild(this.#container);

    this.#tableBox = Utils.createElement("div", [
      "bg-body",
      "d-flex",
      "flex-column",
      "gap-3",
    ]);
    this.#container.append(this.#tableBox);

    this.#list = Utils.createElement("div", ["d-flex", "flex-column", "gap-2"]);
    this.#tableBox.append(this.#list);

    const separator = Utils.createElement("hr", ["my-1"]);
    this.#tableBox.append(separator);

    this.#tableBox.append(this.#buildTypeControls());
    this.#tableBox.append(this.#buildFromAndModeControls());

    // Wire behavior once controls are in the DOM
    this.#wireModeBehavior();

    const addBtn = Utils.createElement("button", [
      "btn",
      "btn-outline-primary",
      "align-self-start",
    ]);
    addBtn.type = "button";
    addBtn.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;
    addBtn.addEventListener("click", () => {
      const tw = this.#collectTimingWindowFromForm();
      const valid = this.#validateAndMarkErrors(tw);
      if (!valid) return;

      this.#addTimingWindow(tw);
    });
    this.#tableBox.append(addBtn);

    this.#renderList();
  }

  /**
   * Re-render the list of existing timing windows.
   *
   * @private
   */
  #renderList() {
    this.#list.innerHTML = "";

    if (this.#timingWindows.length > 0) {
      this.#timingWindows.forEach((tw, index) => {
        const message = this.#buildMessage(tw);
        this.#addRow(index, tw.inclusion, message);
      });
    } else {
      this.#addRow(null, null, "No time windows have been defined");
    }
  }

  /**
   * Build the human-readable summary message for a timing window.
   *
   * @private
   * @param {Object} tw - Timing window object.
   * @returns {string} Summary message describing the timing window.
   */
  #buildMessage(tw) {
    const start = tw.startUtc ?? "";
    let message = `${start.replace(" ", " @ ")} UTC`;

    if (!tw.end) {
      message += " forever";
    } else if (tw.end.atUtc) {
      const endMessage = `${tw.end.atUtc.replace(" ", " @ ")} UTC`;
      message += ` through ${endMessage}`;
    } else if (tw.end.after && !tw.end.repeat) {
      const endMessage = secondsToHumanReadableString(tw.end.after.seconds);
      message += ` for ${endMessage}`;
    } else if (tw.end.after && tw.end.repeat) {
      const periodText = secondsToHumanReadableString(
        tw.end.repeat.period.seconds,
      );
      const times = tw.end.repeat.times;

      if (times == null) {
        message += ` repeat forever with a period of ${periodText}`;
      } else if (times === 1) {
        message += ` repeat once after ${periodText}`;
      } else {
        message += ` repeat ${times} times with a period of ${periodText}`;
      }
    }

    return message;
  }

  /**
   * Add a visual row for a timing window or the empty-state message.
   *
   * @private
   * @param {number|null} index - Index of the timing window in the array, or null for the empty state.
   * @param {string|null} kind - Window kind ("Include" / "Exclude"), case-insensitive.
   * @param {string} message - Human-readable summary.
   */
  #addRow(index, kind, message) {
    if (!kind) {
      const messageHTML = Utils.createElement("div", ["text-muted", "ps-1"]);
      messageHTML.textContent = message;
      this.#list.append(messageHTML);
      return;
    }

    const normalizedKind = Utils.capitalizeFirstLetter(kind);

    const row = Utils.createElement("div", ["input-group", "mb-1"]);
    row.dataset.index = index;

    const badge = Utils.createElement("span", [
      "input-group-text",
      normalizedKind === "Include" ? "bg-success-subtle" : "bg-danger-subtle",
    ]);
    badge.textContent = normalizedKind;

    const summary = Utils.createElement("span", [
      "form-control",
      "fw-semibold",
    ]);
    summary.textContent = message;

    const removeBtn = Utils.createElement("button", ["btn", "btn-danger"]);
    removeBtn.type = "button";
    removeBtn.innerHTML = `<i class="fa-solid fa-minus"></i>`;
    removeBtn.title = "Remove";
    removeBtn.addEventListener("click", () => {
      const rowIndex = Number(row.dataset.index);
      this.#removeTimingWindowAt(rowIndex);
    });

    row.append(badge, summary, removeBtn);
    this.#list.append(row);
  }

  /**
   * Append a timing window to the internal list and re-render.
   *
   * @private
   * @param {Object} tw - Timing window definition object.
   */
  #addTimingWindow(tw) {
    this.#timingWindows.push(tw);
    this.#renderList();
  }

  /**
   * Remove a timing window at the given index and re-render.
   *
   * Safely does nothing if the index is out of bounds.
   *
   * @private
   * @param {number} index - Index of the timing window to remove.
   */
  #removeTimingWindowAt(index) {
    if (!Number.isInteger(index)) return;
    if (index < 0 || index >= this.#timingWindows.length) return;

    this.#timingWindows.splice(index, 1);
    this.#renderList();
  }

  /**
   * Create a radio button group option.
   *
   * @private
   * @param {string} group - Name of the radio group.
   * @param {string} text - Label text and value.
   * @param {boolean} checked - Whether the radio should start checked.
   * @returns {HTMLDivElement} A wrapper containing the radio and label.
   */
  #radio(group, text, checked) {
    const wrapper = Utils.createElement("div", ["form-check", "mb-0"]);

    const input = Utils.createElement("input", ["form-check-input"]);
    input.type = "radio";
    input.name = group;
    input.value = text;
    input.checked = checked;
    input.id = `${this.#idPrefix}-${group}-${text}`;

    const label = Utils.createElement("label", ["form-check-label"]);
    label.textContent = text;
    label.setAttribute("for", input.id);

    wrapper.append(input, label);
    return wrapper;
  }

  /**
   * Build the Include/Exclude type controls (radio group).
   *
   * @private
   * @returns {HTMLDivElement} A container with type radios.
   */
  #buildTypeControls() {
    const group = Utils.createElement("div", ["input-group", "gap-3", "px-2"]);
    group.append(
      this.#radio("type", "Include", true),
      this.#radio("type", "Exclude", false),
    );
    return group;
  }

  #buildFromAndModeControls() {
    const row = Utils.createElement("div", [
      "d-flex",
      "flex-wrap",
      "align-items-start",
      "gap-3",
      "px-2",
    ]);

    const fromGroup = this.#buildFromControls();
    const modeGroup = this.#buildModeControls();

    row.append(fromGroup, modeGroup);
    return row;
  }

  /**
   * Build the "From" block: label + datetime-local + UTC badge.
   *
   * @private
   * @returns {HTMLDivElement} fromContainer
   */
  #buildFromControls() {
    const fromContainer = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const inputId = `${this.#idPrefix}-from`;

    const label = Utils.createElement("label", [
      "input-group-text",
      "text-muted",
    ]);
    label.textContent = "From";
    label.setAttribute("for", inputId);

    const fromInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    fromInput.type = "datetime-local";
    fromInput.style.maxWidth = "170px";
    fromInput.value = getNowForDatetimeLocalUtc();
    fromInput.name = "startUtc";
    fromInput.id = inputId;

    const badge = Utils.createElement("span", ["input-group-text"]);
    badge.textContent = "UTC";

    fromContainer.append(label, fromInput, badge);
    return fromContainer;
  }

  /**
   * Build the right-hand side mode controls: Forever / Through / For + Repeat.
   *
   * @private
   * @returns {HTMLDivElement} modeContainer
   */
  #buildModeControls() {
    const modeContainer = Utils.createElement("div", [
      "d-flex",
      "flex-column",
      "gap-3",
    ]);

    modeContainer.append(this.#buildForeverRow());
    modeContainer.append(this.#buildThroughRow());
    modeContainer.append(this.#buildForRow());
    modeContainer.append(this.#buildRepeatBlock());

    return modeContainer;
  }

  /**
   * Build the "Forever" row: radio only.
   *
   * @private
   * @returns {HTMLDivElement}
   */
  #buildForeverRow() {
    const row = Utils.createElement("div", [
      "d-flex",
      "align-items-start",
      "gap-2",
    ]);
    const foreverRadio = this.#radio("mode", MODES.FOREVER, true);
    row.append(foreverRadio);
    return row;
  }

  #buildThroughRow() {
    const row = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const radio = this.#radio("mode", MODES.THROUGH, false);
    row.append(radio);
    radio.classList.add("me-2");

    const inputsWrapper = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const input = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    input.type = "datetime-local";
    input.style.maxWidth = "170px";
    input.name = "endAtUtc";
    input.id = `${this.#idPrefix}-end-at-utc`;

    const badge = Utils.createElement("span", ["input-group-text"]);
    badge.textContent = "UTC";

    inputsWrapper.append(input, badge);
    row.append(inputsWrapper);

    return row;
  }

  /**
   * Build the "For" row: radio + duration input + suffix.
   *
   * @private
   * @returns {HTMLDivElement}
   */
  #buildForRow() {
    const row = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const radio = this.#radio("mode", MODES.FOR, false);
    row.append(radio);
    radio.classList.add("me-2");

    const inputsWrapper = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const input = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    input.style.maxWidth = "60px";
    input.value = "48:00";
    input.name = "durationHours";
    input.id = `${this.#idPrefix}-duration`;

    const suffix = Utils.createElement("span", ["input-group-text"]);
    suffix.textContent = "hours";

    inputsWrapper.append(input, suffix);
    row.append(inputsWrapper);

    return row;
  }

  #buildRepeatBlock() {
    const block = Utils.createElement("div", [
      "d-flex",
      "flex-column",
      "gap-1",
    ]);

    const repeatRow = Utils.createElement("div", [
      "d-flex",
      "align-items-start",
      "gap-1",
      "ms-4",
    ]);

    const checkbox = Utils.createElement("input", ["form-check-input"]);
    checkbox.type = "checkbox";
    checkbox.checked = false;
    checkbox.name = "repeatEnabled";
    checkbox.classList.add("me-2");

    const checkboxId = `${this.#idPrefix}-repeat-enabled`;
    checkbox.id = checkboxId;

    const label = Utils.createElement("label", ["form-check-label", "me-2"]);
    label.textContent = "Repeat with a period of";
    label.setAttribute("for", checkboxId);

    const periodGroup = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const periodInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    periodInput.style.maxWidth = "75px";
    periodInput.name = "repeatPeriod";
    periodInput.id = `${this.#idPrefix}-repeat-period`;

    const suffix = Utils.createElement("span", ["input-group-text"]);
    suffix.textContent = "hours";

    periodGroup.append(periodInput, suffix);
    repeatRow.append(checkbox, label, periodGroup);
    block.append(repeatRow);

    // Forever repeat
    const foreverRow = Utils.createElement("div", [
      "form-check",
      "mb-0",
      "ms-5",
      "tw-repeat-subrow",
    ]);
    const foreverInput = Utils.createElement("input", ["form-check-input"]);
    foreverInput.type = "radio";
    foreverInput.name = "repeatMode";
    foreverInput.value = REPEAT_MODES.FOREVER;
    foreverInput.checked = true;
    foreverInput.id = `${this.#idPrefix}-repeat-forever`;

    const foreverLabel = Utils.createElement("label", ["form-check-label"]);
    foreverLabel.textContent = "Forever";
    foreverLabel.setAttribute("for", foreverInput.id);

    foreverRow.append(foreverInput, foreverLabel);
    block.append(foreverRow);

    // Times repeat
    const timesRow = Utils.createElement("div", [
      "d-flex",
      "align-items-start",
      "mb-0",
      "ms-5",
      "tw-repeat-subrow",
    ]);
    const timesRadio = Utils.createElement("input", [
      "form-check-input",
      "me-2",
    ]);
    timesRadio.type = "radio";
    timesRadio.name = "repeatMode";
    timesRadio.value = REPEAT_MODES.TIMES;
    timesRadio.id = `${this.#idPrefix}-repeat-times`;

    const timesGroup = Utils.createElement("div", [
      "input-group",
      "input-group-sm",
      "w-auto",
    ]);

    const timesCountInput = Utils.createElement("input", [
      "form-control",
      "form-control-sm",
    ]);
    timesCountInput.style.maxWidth = "50px";
    timesCountInput.type = "number";
    timesCountInput.min = "1";
    timesCountInput.name = "repeatTimes";
    timesCountInput.id = `${this.#idPrefix}-repeat-times-count`;

    const timesLabel = Utils.createElement("label", ["input-group-text"]);
    timesLabel.textContent = "times";
    timesLabel.setAttribute("for", timesCountInput.id);

    timesGroup.append(timesCountInput, timesLabel);
    timesRow.append(timesRadio, timesGroup);
    block.append(timesRow);

    return block;
  }

  /**
   * Wire dynamic behavior for mode + repeat controls.
   *
   * @private
   */
  #wireModeBehavior() {
    const modeRadios = this.#container.querySelectorAll('input[name="mode"]');

    const throughInput = this.#container.querySelector(
      `#${this.#idPrefix}-end-at-utc`,
    );
    const throughInputs = throughInput
      ? throughInput.closest(".input-group")
      : null;

    const forInput = this.#container.querySelector(
      `#${this.#idPrefix}-duration`,
    );
    const forInputs = forInput ? forInput.closest(".input-group") : null;

    // Repeat
    const repeatCheckbox = this.#container.querySelector(
      `#${this.#idPrefix}-repeat-enabled`,
    );

    const repeatBlock = repeatCheckbox
      ? repeatCheckbox.closest(".d-flex.flex-column") ||
        repeatCheckbox.closest("div")
      : null;

    const repeatSubRows = repeatBlock
      ? repeatBlock.querySelectorAll(".tw-repeat-subrow")
      : [];

    const repeatPeriodInput = this.#container.querySelector(
      `#${this.#idPrefix}-repeat-period`,
    );

    const repeatModeRadios =
      this.#container.querySelectorAll('input[name="repeatMode"]') || [];

    const repeatForeverInput = Array.from(repeatModeRadios).find(
      (r) => r.value === REPEAT_MODES.FOREVER,
    );
    const repeatTimesInput = Array.from(repeatModeRadios).find(
      (r) => r.value === REPEAT_MODES.TIMES,
    );

    const timesCountInput = this.#container.querySelector(
      `#${this.#idPrefix}-repeat-times-count`,
    );

    const hideEl = (el) => el && el.classList.add("d-none");
    const showEl = (el) => el && el.classList.remove("d-none");

    const updateModeVisibility = (modeValue) => {
      const isForever = modeValue === MODES.FOREVER;
      const isThrough = modeValue === MODES.THROUGH;
      const isFor = modeValue === MODES.FOR;

      if (isThrough) {
        showEl(throughInputs);
        if (throughInput && !throughInput.value) {
          throughInput.value = getNowForDatetimeLocalUtc();
        }
      } else {
        hideEl(throughInputs);
      }

      if (isFor) {
        showEl(forInputs);
        showEl(repeatBlock);
      } else {
        hideEl(forInputs);
        hideEl(repeatBlock);
      }

      if (isForever) {
        hideEl(throughInputs);
        hideEl(forInputs);
        hideEl(repeatBlock);
      }
    };

    const updateTimesInputState = () => {
      if (!repeatCheckbox || !timesCountInput || !repeatTimesInput) return;

      const repeatEnabled = repeatCheckbox.checked;
      const timesSelected = repeatTimesInput.checked;
      const shouldEnableTimes = repeatEnabled && timesSelected;

      timesCountInput.disabled = !shouldEnableTimes;

      if (shouldEnableTimes && !timesCountInput.value) {
        timesCountInput.value = "1";
      } else if (!shouldEnableTimes) {
        timesCountInput.value = "";
      }
    };

    const updateRepeatVisibility = (enabled) => {
      repeatSubRows.forEach((row) => {
        row.classList.toggle("d-none", !enabled);
      });

      if (repeatBlock) {
        const repeatInputs = repeatBlock.querySelectorAll("input");
        repeatInputs.forEach((input) => {
          if (input === repeatCheckbox) return;
          input.disabled = !enabled;
        });
      }

      if (repeatPeriodInput) {
        if (enabled && !repeatPeriodInput.value) {
          repeatPeriodInput.value = "60:00:00";
        } else if (!enabled) {
          repeatPeriodInput.value = "";
        }
      }

      updateTimesInputState();
    };

    modeRadios.forEach((radio) => {
      radio.addEventListener("change", (event) => {
        if (event.target.checked) {
          updateModeVisibility(event.target.value);
        }
      });
    });

    if (repeatCheckbox) {
      repeatCheckbox.addEventListener("change", (event) => {
        updateRepeatVisibility(event.target.checked);
      });
    }

    if (repeatTimesInput) {
      repeatTimesInput.addEventListener("change", updateTimesInputState);
    }
    if (repeatForeverInput) {
      repeatForeverInput.addEventListener("change", updateTimesInputState);
    }

    updateModeVisibility(MODES.FOREVER);
    updateRepeatVisibility(repeatCheckbox ? repeatCheckbox.checked : false);
    updateTimesInputState();
  }
  /**
   * Build a timing window object from the current form controls.
   *
   * @private
   * @returns {{inclusion: string, startUtc: string, end: (null|Object)}} Timing window object.
   */
  #collectTimingWindowFromForm() {
    const typeInput = this.#container.querySelector(
      'input[name="type"]:checked',
    );

    const inclusion = typeInput?.value?.toUpperCase() ?? "INCLUDE";

    const fromInput = this.#container.querySelector(`#${this.#idPrefix}-from`);
    const startUtc = fromInput?.value ?? "";

    const modeInput = this.#container.querySelector(
      'input[name="mode"]:checked',
    );
    const mode = modeInput?.value ?? MODES.FOREVER;

    let end = null;

    switch (mode) {
      case MODES.FOREVER:
        end = this.#buildEndForever();
        break;
      case MODES.THROUGH:
        end = this.#buildEndThrough();
        break;
      case MODES.FOR:
        end = this.#buildEndFor();
        break;
      default:
        end = null;
    }

    return {
      inclusion,
      startUtc,
      end,
    };
  }
  /**
   * Build `end` for Forever mode.
   *
   * @private
   * @returns {null}
   */
  #buildEndForever() {
    return null;
  }

  /**
   * Build `end` for Through mode.
   *
   * @private
   * @returns {null|{atUtc: string}}
   */
  #buildEndThrough() {
    const throughInput = /** @type {HTMLInputElement|null} */ (
      this.#container.querySelector(`#${this.#idPrefix}-end-at-utc`)
    );
    const atRaw = throughInput?.value ?? "";

    if (!atRaw) return null;

    return { atUtc: atRaw };
  }

  /**
   * Build `repeat` block for For mode, if enabled.
   *
   * @private
   * @returns {null|{times: (number|null), period: {seconds: number}}}
   */
  #buildRepeat() {
    const repeatCheckbox = /** @type {HTMLInputElement|null} */ (
      this.#container.querySelector(`#${this.#idPrefix}-repeat-enabled`)
    );
    const repeatEnabled = repeatCheckbox?.checked ?? false;
    if (!repeatEnabled) return null;

    const repeatModeInput = /** @type {HTMLInputElement|null} */ (
      this.#container.querySelector('input[name="repeatMode"]:checked')
    );
    const repeatMode = repeatModeInput?.value ?? REPEAT_MODES.FOREVER;

    const periodInput = /** @type {HTMLInputElement|null} */ (
      this.#container.querySelector(`#${this.#idPrefix}-repeat-period`)
    );
    const periodRaw = periodInput?.value ?? "";
    const periodSeconds = parseDurationToSeconds(periodRaw);

    let times = null;
    if (repeatMode === REPEAT_MODES.TIMES) {
      const timesInput = /** @type {HTMLInputElement|null} */ (
        this.#container.querySelector(`#${this.#idPrefix}-repeat-times-count`)
      );
      const timesRaw = timesInput?.value ?? "";
      const timesValue = Number(timesRaw);
      times = Number.isFinite(timesValue) ? timesValue : null;
    }

    return {
      times,
      period: {
        seconds: periodSeconds,
      },
    };
  }

  /**
   * Build `end` for For mode.
   *
   * @private
   * @returns {{after: {seconds: number}, repeat: (null|{times: (number|null), period: {seconds: number}})}}
   */
  #buildEndFor() {
    const durationInput = /** @type {HTMLInputElement|null} */ (
      this.#container.querySelector(`#${this.#idPrefix}-duration`)
    );
    const durationRaw = durationInput?.value ?? "";
    const durationSeconds = parseDurationToSeconds(durationRaw);

    const repeat = this.#buildRepeat();

    return {
      after: {
        seconds: durationSeconds,
      },
      repeat,
    };
  }
  /**
   * Toggle error style on a form input (no feedback text).
   *
   * @private
   * @param {HTMLElement|null} el
   * @param {boolean} isError
   */
  #markFieldError(el, isError) {
    if (!el) return;
    el.classList.toggle("is-invalid", isError);
  }
  /**
   * Validate the start time field.
   *
   * @param {{ startUtc: string }} tw - Timing window object.
   * @returns {boolean} True if valid.
   */
  #validateStart(tw) {
    const startInput = this.#container.querySelector('input[name="startUtc"]');
    const value = tw.startUtc;
    const d = value ? new Date(value) : null;
    const err = !(d && !Number.isNaN(d.getTime()));

    this.#markFieldError(startInput, err);
    return !err;
  }

  /**
   * Validate the "Through" mode end time.
   *
   * @param {{ startUtc: string, end: { atUtc?: string } | null }} tw - Timing window object.
   * @returns {boolean} True if valid.
   */
  #validateThrough(tw) {
    const start = tw.startUtc ? new Date(tw.startUtc) : null;

    const endInput = this.#container.querySelector('input[name="endAtUtc"]');
    const endRaw = tw.end?.atUtc ?? "";
    const end = endRaw ? new Date(endRaw) : null;

    const err = !(start && end && end > start);
    this.#markFieldError(endInput, err);

    return !err;
  }

  /**
   * Validate the "For" mode duration and repeat.
   *
   * @param {{ end: { after?: { seconds: number }, repeat?: { period: { seconds: number }, times: (number|null) } } | null }} tw
   * @returns {boolean} True if valid.
   */
  #validateForAndRepeat(tw) {
    let ok = true;

    const durationInput = this.#container.querySelector(
      'input[name="durationHours"]',
    );
    const durationSeconds = parseDurationToSeconds(durationInput?.value ?? "");

    const durErr = !(Number.isFinite(durationSeconds) && durationSeconds > 0);
    this.#markFieldError(durationInput, durErr);
    ok &&= !durErr;

    const repeatEnabled =
      this.#container.querySelector('input[name="repeatEnabled"]')?.checked ??
      false;

    if (repeatEnabled && tw.end?.repeat) {
      const periodInput = this.#container.querySelector(
        'input[name="repeatPeriod"]',
      );
      const pSeconds = tw.end.repeat.period.seconds;

      const pErr = !(Number.isFinite(pSeconds) && pSeconds > 0);
      this.#markFieldError(periodInput, pErr);
      ok &&= !pErr;

      if (tw.end.repeat.times != null) {
        const timesInput = this.#container.querySelector(
          'input[name="repeatTimes"]',
        );
        const times = tw.end.repeat.times;

        const tErr = !(Number.isInteger(times) && times > 0);
        this.#markFieldError(timesInput, tErr);
        ok &&= !tErr;
      }
    }

    return ok;
  }

  /**
   * Validate a timing window and mark invalid inputs.
   *
   * @param {Object} tw - Timing window object.
   * @returns {boolean} True if valid.
   */
  #validateAndMarkErrors(tw) {
    let ok = this.#validateStart(tw);

    const mode =
      this.#container.querySelector('input[name="mode"]:checked')?.value ??
      MODES.FOREVER;

    if (mode === MODES.THROUGH) {
      ok &&= this.#validateThrough(tw);
    } else if (mode === MODES.FOR) {
      ok &&= this.#validateForAndRepeat(tw);
    }

    return ok;
  }

  getValues() {
    return this.#timingWindows.map((tw) => ({
      inclusion: tw.inclusion,
      startUtc: tw.startUtc,
      end: tw.end ? structuredClone(tw.end) : null,
    }));
  }
}
