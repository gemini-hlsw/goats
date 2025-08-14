/**
 * ToastManager handles creation and display of Bootstrap toasts with icons and color-coded alerts.
 */
class ToastManager {
  /**
   * Create a ToastManager.
   * @param {HTMLElement|string} container - A DOM element or ID of the container where toasts will
   * be appended.
   * @param {Object} [options] - Default behavior options.
   * @param {number} [options.delay=6000] - Default delay in ms.
   * @param {boolean} [options.autohide=true] - Default auto-hide behavior.
   */
  constructor(container = "toastContainer", options = {}) {
    this.container =
      typeof container === "string" ? document.getElementById(container) : container;

    if (!this.container) {
      throw new Error("Toast container not found.");
    }

    this.options = {
      delay: 6000,
      autohide: true,
      ...options,
    };
  }

  /**
   * Display a toast notification.
   * @param {Object} notification - The notification payload.
   * @param {string} notification.label - Short heading for the toast.
   * @param {string} notification.message - Main body content of the toast.
   * @param {string} notification.color - One of "info", "success", "warning", or "danger".
   * @param {Object} [options] - Toast behavior options.
   * @param {number} [options.delay] - Delay override.
   * @param {boolean} [options.autohide] - Autohide override.
   */
  show(notification, options = {}) {
    const toastEl = this.#create(notification);
    this.container.appendChild(toastEl);

    const toastOptions = { ...this.options, ...options };
    const toast = new bootstrap.Toast(toastEl, toastOptions);
    toast.show();
  }

  test() {
    toast.show({
      label: "Testing toast",
      message: "This is a test. This is how it will appear.",
      color: "info",
    });
  }

  /**
   * Create a fully formed toast DOM element.
   * @param {Object} notification
   * @param {number} delay
   * @returns {HTMLElement}
   */
  #create(notification) {
    const { label, message, color } = notification;

    const toast = document.createElement("div");
    toast.classList.add(
      "toast",
      "border-start",
      `border-${color}`,
      "border-top-0",
      "border-bottom-0",
      "border-end-0",
      "border-3"
    );
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "assertive");
    toast.setAttribute("aria-atomic", "true");

    const header = document.createElement("div");
    header.classList.add("toast-header");

    const icon = document.createElement("i");
    icon.classList.add("fa-solid", this.#getIconClass(color), "pe-2", `text-${color}`);
    header.appendChild(icon);

    const strong = document.createElement("strong");
    strong.classList.add("me-auto");
    strong.textContent = label;
    header.appendChild(strong);

    const closeBtn = document.createElement("button");
    closeBtn.classList.add("btn-close");
    closeBtn.setAttribute("data-bs-dismiss", "toast");
    closeBtn.setAttribute("aria-label", "Close");
    header.appendChild(closeBtn);

    const body = document.createElement("div");
    body.classList.add("toast-body");

    const text = document.createElement("p");
    text.classList.add("mb-0");
    text.innerHTML = message;
    body.appendChild(text);

    toast.appendChild(header);
    toast.appendChild(body);

    return toast;
  }

  /**
   * Maps color names to FontAwesome icon classes.
   * @param {string} color
   * @returns {string}
   */
  #getIconClass(color) {
    switch (color) {
      case "warning":
        return "fa-triangle-exclamation";
      case "danger":
        return "fa-circle-xmark";
      case "info":
        return "fa-comment";
      case "success":
        return "fa-circle-check";
      default:
        return "fa-circle-info";
    }
  }
}
