/**
 * A static utility class that provides basic string formatting helpers
 * commonly used to convert enum-style keys into human-readable labels.
 *
 * These methods are used to display labels in forms and UI components
 * with proper capitalization and spacing.
 */

class Formatters {
  /**
   * Replaces all underscores in the string with spaces.
   *
   * @param {string} text - The input string.
   * @returns {string} The transformed string with spaces.
   */
  static replaceUnderscore(text) {
    return text.replace(/_/g, " ");
  }

  /**
   * Capitalizes the first letter of the string and lowercases the rest.
   *
   * @param {string} text - The input string.
   * @returns {string} The transformed string.
   */
  static capitalizeFirstLetter(text) {
    return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
  }

  /**
   * Converts an underscore-separated string to title case.
   * Capitalizes the first letter of each word and lowercases the rest.
   *
   * @param {string} text - The input string.
   * @returns {string} The title-cased string.
   */
  static titleCaseFromUnderscore(text) {
    return text
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(" ");
  }
}
