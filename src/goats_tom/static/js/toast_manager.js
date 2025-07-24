/**
 * ToastManager handles creation and display of Bootstrap toasts with icons and color-coded alerts.
 */
class ToastManager {
  /**
   * Create a ToastManager.
   * @param {HTMLElement|string} container - A DOM element or ID of the container where toasts will be appended.
   */
  constructor(container = "toastContainer") {
    this.container =
      typeof container === "string" ? document.getElementById(container) : container;

    if (!this.container) {
      throw new Error("Toast container not found.");
    }
  }

  /**
   * Display a toast notification.
   * @param {Object} notification - The notification payload.
   * @param {string} notification.label - Short heading for the toast.
   * @param {string} notification.message - Main body content of the toast.
   * @param {string} notification.color - One of "info", "success", "warning", or "danger".
   * @param {number} [delay=6000] - Time in ms before toast auto-hides.
   */
  show(notification, delay = 6000) {
    const toastEl = this.#create(notification);
    this.container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { autohide: true, delay });
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
    text.textContent = message;
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
