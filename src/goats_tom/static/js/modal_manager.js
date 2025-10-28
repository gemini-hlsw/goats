/**
 * Manages a single Bootstrap modal instance with dynamic content and configuration.
 */
class ModalManager {
  /**
   * Creates a new ModalManager instance and appends the modal to the specified parent element.
   * @param {HTMLElement} [parentElement=document.body] - The element to which the modal will be
   * attached.
   */
  constructor(parentElement = document.body) {
    this.parentElement = parentElement;
    this.modalId = "app-modal";
    this._initModal();
  }

  /**
   * Initializes the modal DOM structure and appends it to the parent element.
   * @private
   */
  _initModal = () => {
    this.modalEl = document.createElement("div");
    this.modalEl.id = this.modalId;
    this.modalEl.className = "modal fade";
    this.modalEl.tabIndex = -1;
    this.modalEl.setAttribute("aria-hidden", "true");

    this.modalEl.innerHTML = `
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h1 class="modal-title fs-5"></h1>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body"></div>
          <div class="modal-footer d-none"></div>
        </div>
      </div>
    `;

    this.parentElement.appendChild(this.modalEl);

    this.dialogEl = this.modalEl.querySelector(".modal-dialog");
    this.contentEl = this.modalEl.querySelector(".modal-content");
    this.titleEl = this.modalEl.querySelector(".modal-title");
    this.bodyEl = this.modalEl.querySelector(".modal-body");
    this.footerEl = this.modalEl.querySelector(".modal-footer");
    this.bootstrapModal = null;
  };

  /**
   * Displays the modal with the provided configuration.
   * @param {Object} options - Modal configuration.
   * @param {string} [options.title] - Modal title HTML.
   * @param {string} [options.body] - Modal body HTML.
   * @param {string} [options.footer] - Modal footer HTML.
   * @param {boolean|string} [options.backdrop=true] - `true`, `false`, or `'static'`.
   * @param {boolean} [options.keyboard=true] - If `false`, disables ESC key dismissal.
   * @param {string[]} [options.dialogClasses=[]] - Extra classes to apply to `.modal-dialog`.
   * @param {string[]} [options.contentClasses=[]] - Extra classes to apply to `.modal-content`.
   */
  show = (options = {}) => {
    const {
      title = "",
      body = "",
      footer = "",
      backdrop = true,
      keyboard = true,
      dialogClasses = [],
      contentClasses = [],
    } = options;

    this.titleEl.innerHTML = title;
    this.bodyEl.innerHTML = body;

    if (footer) {
      this.footerEl.innerHTML = footer;
      this.footerEl.classList.remove("d-none");
    } else {
      this.footerEl.classList.add("d-none");
    }

    this.dialogEl.className = "modal-dialog";
    dialogClasses.forEach((cls) => this.dialogEl.classList.add(cls));

    this.contentEl.className = "modal-content";
    contentClasses.forEach((cls) => this.contentEl.classList.add(cls));

    if (this.bootstrapModal) {
      this.bootstrapModal.dispose();
    }

    this.bootstrapModal = new bootstrap.Modal(this.modalEl, {
      backdrop,
      keyboard,
    });

    this.bootstrapModal.show();
  };

  /**
   * Hides the modal.
   */
  hide = () => {
    this.bootstrapModal?.hide();
  };

  /**
   * Updates the modal title, body, and/or footer content.
   * @param {Object} updates - Partial updates.
   * @param {string} [updates.title] - New title HTML.
   * @param {string} [updates.body] - New body HTML.
   * @param {string} [updates.footer] - New footer HTML.
   */
  update = ({ title, body, footer } = {}) => {
    if (title !== undefined) this.titleEl.innerHTML = title;
    if (body !== undefined) this.bodyEl.innerHTML = body;
    if (footer !== undefined) {
      this.footerEl.innerHTML = footer;
      this.footerEl.classList.remove("d-none");
    }
  };

  /**
   * Appends additional content to the modal body or footer.
   * @param {Object} content - Content to append.
   * @param {string} [content.body] - HTML to append to the body.
   * @param {string} [content.footer] - HTML to append to the footer.
   */
  append = ({ body, footer } = {}) => {
    if (body) this.bodyEl.insertAdjacentHTML("beforeend", body);
    if (footer) {
      this.footerEl.insertAdjacentHTML("beforeend", footer);
      this.footerEl.classList.remove("d-none");
    }
  };

  /**
   * Clears the modal content and resets classes.
   */
  clear = () => {
    this.titleEl.innerHTML = "";
    this.bodyEl.innerHTML = "";
    this.footerEl.innerHTML = "";
    this.dialogEl.className = "modal-dialog";
    this.contentEl.className = "modal-content";
    this.footerEl.classList.add("d-none");
  };
}
