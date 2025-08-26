/**
 * Provides static utility functions for DOM manipulation and general utility tasks.
 */
class Utils {
  /**
   * Returns the first element within the document that matches the specified selector.
   * @param {string} selector - The CSS selector to match elements against.
   * @param {Element|Document} [scope=document] - The root element to search within.
   * @return {Element|null} The first matching element or null if no matches are found.
   */
  static qs(selector, scope = document) {
    return scope.querySelector(selector);
  }

  /**
   * Returns a list of elements within the document that match the specified selector.
   * @param {string} selector - The CSS selector to match elements against.
   * @param {Element|Document} [scope=document] - The root element to search within.
   * @return {NodeList} A NodeList of matching elements.
   */
  static qsa(selector, scope = document) {
    return scope.querySelectorAll(selector);
  }

  /**
   * Adds an event listener to a specified element.
   * @param {EventTarget} target - The target element to attach the event listener to.
   * @param {string} type - The type of event to listen for.
   * @param {Function} callback - The function to be called when the event is triggered.
   * @param {boolean} [useCapture=false] - A Boolean indicating whether the event should be
   * captured before it reaches the target (capture phase) or after it bubbles up (bubbling phase).
   */
  static on(target, type, callback, useCapture = false) {
    target.addEventListener(type, callback, useCapture);
  }

  /**
   * Delegates an event to a target element based on a selector.
   * @param {Element} target - The element on which to listen for the event.
   * @param {string} selector - The selector to match against when the event is triggered.
   * @param {string} type - The type of event to delegate.
   * @param {Function} handler - The function to execute when the event occurs on an element
   * matching the selector.
   */
  static delegate(target, selector, type, handler) {
    // Determine if the event should be captured during the capture phase.
    // This is necessary for events that do not bubble naturally, such as "focus" or "blur".
    const useCapture = type === "blur" || type === "focus";

    function dispatchEvent(event) {
      const targetElement = event.target;
      // Find all elements within the target that match the provided selector.
      const potentialElements = Utils.qsa(selector, target);
      const hasMatch = Array.from(potentialElements).includes(targetElement);

      // If there's a match and the handler is supposed to be executed, call the handler function
      // and set 'this' to the targetElement which is the element that matched the selector.
      if (hasMatch) handler.call(targetElement, event);
    }

    // Attach the dispatchEvent function as an event listener to the target.
    // This setup allows the event to be captured at the target or bubble up to it, depending on
    // the event type.
    Utils.on(target, type, dispatchEvent, useCapture);
  }

  static capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1).toLowerCase();
  }

  static isEmpty(obj) {
    return Object.keys(obj).length === 0 && obj.constructor === Object;
  }

  /**
   * Creates a new HTML element with optional class names.
   * @param {string} tag The tag name of the element to create.
   * @param {string | string[]} classNames The class name(s) to add to the element.
   * @returns {Element} The newly created element.
   */
  static createElement(tag, classNames) {
    const element = document.createElement(tag);
    if (classNames) {
      if (Array.isArray(classNames)) {
        element.classList.add(...classNames);
      } else {
        element.classList.add(classNames);
      }
    }
    return element;
  }

  /**
   * Escapes HTML characters to prevent XSS and ensure proper display of text.
   * @param {string} str The string to escape.
   * @returns {string} The escaped HTML string.
   */
  static escapeHTML(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  static getByPath(obj, p) {
    return p
      .replace(/\[(\d+)]/g, ".$1")
      .split(".")
      .reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);
  }

  /**
   * Formats a snake_case string into a human-readable title format with spaces and capitalization.
   * Also converts "Id" to all uppercase.
   * @param {string} text The text to format, typically a key from a documentation object.
   * @returns {string} The formatted text with underscores replaced by spaces and each word
   * capitalized.
   */
  static formatDisplayText(text) {
    return text
      .toLowerCase()
      .replace(/_/g, " ")
      .split(" ")
      .map((word) => {
        if (word.toLowerCase() === "id") {
          return "ID";
        }
        return word.charAt(0).toUpperCase() + word.slice(1);
      })
      .join(" ");
  }

  /**
   * Generates a label indicating the number of files.
   * @param {number} count The number of files.
   * @returns {string} A formatted label displaying the number of files.
   */
  static getFileCountLabel(count) {
    return count === 1 ? "(1 file)" : `(${count} files)`;
  }

  /**
   * Truncates text to a specified length and appends an ellipsis ('...') if the text is longer
   * than the maximum length.
   * @param {string} text - The text to be truncated.
   * @param {number} [maxLength=25] - The maximum length of the text after truncation.
   * @returns {string} The truncated text with an ellipsis if it was cut off.
   */
  static truncateText(text, maxLength = 25) {
    // Split the text by the pipe character and process each part.
    return text
      .split("|")
      .map((part) => {
        if (part.length > maxLength) {
          // Subtract 4 from maxLength to accommodate the ellipsis and space.
          return part.substring(0, maxLength - 4) + "... ";
        }
        return part;
      })
      .join("|"); // Join the processed parts back with the pipe character.
  }

  /**
   * Ensures that the provided operation lasts at least the specified minimum duration.
   * If no operation is provided, the function will simply wait for the minimum duration.
   *
   * @param {Promise} [operationPromise=Promise.resolve()] - The operation to wait for. Defaults to
   * an immediately resolved promise if not provided.
   * @param {number} [minDuration=500] - The minimum duration in milliseconds to wait. Defaults to
   * 500 milliseconds if not provided.
   * @returns {Promise} A promise that resolves once both the operation and the minimum duration
   * have completed.
   */
  static ensureMinimumDuration(
    operationPromise = Promise.resolve(),
    minDuration = 500
  ) {
    const minDurationPromise = new Promise((resolve) =>
      setTimeout(resolve, minDuration)
    );
    return Promise.all([operationPromise, minDurationPromise]);
  }
}
