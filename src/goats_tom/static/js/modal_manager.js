/**
 * Manages a Bootstrap modal instance, providing methods to show, hide, update, and manipulate
 * modal content.
 */
class ModalManager {
  /** @type {HTMLElement} @private */
  #parentElement;
  /** @type {boolean} @private */
  #debug;
  /** @type {string} @private */
  #debugTag = "[ModalManager]";
  /** @type {string} @private */
  #id = "modalManager";
  /** @type {HTMLElement} @private */
  #element;
  /** @type {HTMLElement} @private */
  #content;
  /** @type {HTMLElement} @private */
  #title;
  /** @type {HTMLElement} @private */
  #body;
  /** @type {HTMLElement} @private */
  #footer;
  /** @type {HTMLElement} @private */
  #dialog;
  /** @type {bootstrap.Modal | null} @private */
  #bootstrapModal;

  /**
   * Creates a new ModalManager instance.
   *
   * @param {HTMLElement} parentElement - DOM element to which the modal will be attached.
   * @param {Object} [options={}] - Configuration options.
   * @param {boolean} [options.debug=false] - Enable debug logging.
   */
  constructor(parentElement, { debug = false } = {}) {
    if (!(parentElement instanceof HTMLElement)) {
      this.#logDebug("Invalid parent element provided.");
      throw new Error("ModalManager expects an HTMLElement as the parent.");
    }

    this.#parentElement = parentElement;
    this.#debug = debug;

    // Create modal element.
    this.#element = this.#create();

    // Assign modal parts.
    this.#content = this.#element.querySelector(".modal-content");
    this.#title = this.#element.querySelector(".modal-title");
    this.#body = this.#element.querySelector(".modal-body");
    this.#footer = this.#element.querySelector(".modal-footer");
    this.#dialog = this.#element.querySelector(".modal-dialog");

    // Append modal to parent element.
    this.#parentElement.appendChild(this.#element);

    // Set bootstrap modal instance to null.
    this.#bootstrapModal = null;
  }

  /**
   * Enable or disable debug logging at runtime.
   * @param {boolean} flag
   */
  setDebug(flag) {
    this.#logDebug(`Setting debug to ${flag}`);
    this.#debug = flag;
  }

  /**
   * Logs a debug message if debugging is enabled.
   *
   * @param {string} message - The message to log.
   * @private
   */
  #logDebug(message) {
    if (this.#debug) console.debug(`${this.#debugTag} ${message}`);
  }

  /**
   * Creates the base modal element.
   * @returns {HTMLElement} The root modal element.
   * @private
   */
  #create() {
    this.#logDebug(`Creating modal with ID: ${this.#id}`);
    const modal = document.createElement("div");
    modal.classList.add("modal", "fade");
    modal.id = this.#id;
    modal.tabIndex = -1;
    const titleId = `${this.#id}Label`;
    modal.setAttribute("aria-labelledby", titleId);
    modal.setAttribute("aria-hidden", "true");
    modal.innerHTML = `
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h1 class="modal-title fs-5" id="${titleId}"></h1>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body"></div>
          <div class="modal-footer d-none"></div>
        </div>
      </div>
    `;

    return modal;
  }

  /**
   * Shows the modal with specified configuration options.
   *
   * @param {Object} [options={}] - Modal display options.
   * @param {string} [options.title=""] - Modal title HTML.
   * @param {string} [options.body=""] - Modal body HTML.
   * @param {string} [options.footer=""] - Modal footer HTML.
   * @param {boolean|string} [options.backdrop=true] - `true`, `false`, or `"static"` to control
   * backdrop behavior.
   * @param {boolean} [options.focus=true] - Whether to focus the modal when shown.
   * @param {boolean} [options.keyboard=true] - Whether to close modal on ESC key.
   * @param {string[]} [options.dialogClasses=[]] - Additional classes to apply to `.modal-dialog`.
   * @param {string[]} [options.contentClasses=[]] - Additional classes to apply to `.
   * modal-content`.
   */
  show({
    title = "",
    body = "",
    footer = "",
    backdrop = true,
    focus = true,
    keyboard = true,
    dialogClasses = [],
    contentClasses = [],
  } = {}) {
    this.#logDebug("Showing modal");
    this.#title.innerHTML = title;
    this.#body.innerHTML = body;

    if (footer) {
      this.#footer.innerHTML = footer;
      this.#footer.classList.remove("d-none");
    } else {
      this.#footer.classList.add("d-none");
    }

    this.#dialog.className = "modal-dialog";
    dialogClasses.forEach((cls) => this.#dialog.classList.add(cls));

    this.#content.className = "modal-content";
    contentClasses.forEach((cls) => this.#content.classList.add(cls));

    if (this.#bootstrapModal) {
      this.#bootstrapModal.dispose();
    }

    this.#bootstrapModal = new bootstrap.Modal(this.#element, {
      backdrop,
      keyboard,
      focus,
    });

    this.#bootstrapModal.show();
  }

  /**
   * Hides the modal.
   */
  hide() {
    this.#logDebug("Hiding modal");
    this.#bootstrapModal?.hide();
  }

  /**
   * Updates modal sections with new content.
   *
   * @param {Object} [options={}] - Update options.
   * @param {string} [options.title] - New modal title HTML. Default is unchanged.
   * @param {string} [options.body] - New modal body HTML. Default is unchanged.
   * @param {string} [options.footer] - New modal footer HTML. Default is unchanged.
   */
  update({ title, body, footer } = {}) {
    if (title !== undefined) {
      this.#logDebug("Updating modal title");
      this.#title.innerHTML = title;
    }
    if (body !== undefined) {
      this.#logDebug("Updating modal body");
      this.#body.innerHTML = body;
    }
    if (footer !== undefined) {
      this.#logDebug("Updating modal footer");
      this.#footer.innerHTML = footer;
      this.#footer.classList.remove("d-none");
    }
    // Call handleUpdate() to readjust the modal's position in case a scrollbar appears/disappears.
    this.#handleUpdate();
  }

  /**
   * Triggers Bootstrap's handleUpdate method to recalculate layout.
   * @private
   */
  #handleUpdate() {
    this.#logDebug("Handling modal update");
    this.#bootstrapModal?.handleUpdate();
  }

  /**
   * Appends additional content to the modal body or footer.
   *
   * @param {Object} [options={}] - Append options.
   * @param {string} [options.body] - HTML to append to body.
   * @param {string} [options.footer] - HTML to append to footer.
   */
  append({ body, footer } = {}) {
    this.#logDebug("Appending to modal content");
    if (body !== undefined) {
      this.#logDebug("Appending to modal body");
      this.#body.insertAdjacentHTML("beforeend", body);
    }
    if (footer !== undefined) {
      this.#logDebug("Appending to modal footer");
      this.#footer.insertAdjacentHTML("beforeend", footer);
      this.#footer.classList.remove("d-none");
    }
    // Call handleUpdate() to readjust the modal's position in case a scrollbar appears/disappears.
    this.#handleUpdate();
  }

  /**
   * Clears all modal content and resets class names.
   */
  clear() {
    this.#logDebug("Clearing modal content");
    this.#title.innerHTML = "";
    this.#body.innerHTML = "";
    this.#footer.innerHTML = "";
    this.#dialog.className = "modal-dialog";
    this.#content.className = "modal-content";
    this.#footer.classList.add("d-none");
  }

  /**
   * Test method to display a sample modal.
   */
  test() {
    this.#logDebug("Running ModalManager test");
    this.show({
      title: "Test Modal",
      body: "<p>This is a test modal body.</p>",
      footer:
        '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>',
      dialogClasses: ["modal-lg"],
      contentClasses: [],
    });
  }
}
