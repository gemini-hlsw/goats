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
   * Extracts the discovery survey suffix from a GOATS subtitle.
   * Subtitles written by GOATS look like "GOATS:<version>[:<survey>]".
   *
   * @param {*} subtitle - The observation subtitle.
   * @returns {string} The survey, or an empty string when there is none.
   */
  static discoverySurveyFromSubtitle(subtitle) {
    if (typeof subtitle !== "string") return "";
    const parts = subtitle.split(":");
    if (parts[0] !== "GOATS" || parts.length < 3) return "";
    return parts.slice(2).join(":").trim();
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
