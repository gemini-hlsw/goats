/**
 * Simplifies making fetch requests by encapsulating common settings and behaviors.
 */
class API {
  /**
   * Initializes a new instance of the API class.
   * @param {string} baseUrl - The base URL for all requests made by this instance.
   */
  static #instance = null;

  constructor(baseUrl, csrfToken) {
    // Singleton design.
    if (API.#instance) {
      return API.#instance;
    }
    API.#instance = this;

    this.baseUrl = baseUrl;
    this.defaultHeaders = {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    };
  }

  /**
   * Performs a fetch request with default settings and error handling.
   * @param {string} endpoint - The endpoint to append to the base URL.
   * @param {Object} [options={}] - Additional options for the fetch request.
   * @returns {Promise<Object|null>} - A promise resolving to the parsed JSON data or `null` for 
   * empty responses.
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;

    // Merge provided headers with defaults.
    options.headers = { ...this.defaultHeaders, ...options.headers };

    // If the body is FormData, remove the 'Content-Type' header to let the browser set it.
    if (options.body instanceof FormData) {
      delete options.headers["Content-Type"];
    }

    try {
      const response = await fetch(url, { ...options, credentials: "same-origin" });

      if (!response.ok) {
        throw response;
      }

      // Check if the response has a JSON content-type or is empty.
      const contentType = response.headers.get("Content-Type");
      if (contentType && contentType.includes("application/json")) {
        return await response.json();
      }
      return null;
    } catch (error) {
      throw error;
    }
  }

  /**
   * Performs a GET request.
   * @param {string} endpoint - The endpoint for the GET request.
   * @param {Object} [options={}] - Additional options for the GET request.
   * @returns {Promise<Object>} - A promise resolving to the response data.
   */
  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: "GET" });
  }

  /**
   * Performs a POST request.
   * @param {string} endpoint - The endpoint for the POST request.
   * @param {Object} body - The body data to send with the POST request.
   * @param {Object} [options={}] - Additional options for the POST request.
   * @param {boolean} [stringify=true] - Whether to stringify the body.
   * @returns {Promise<Object>} - A promise resolving to the response data.
   */
  post(endpoint, body, options = {}, stringify = true) {
    return this.request(endpoint, {
      ...options,
      method: "POST",
      body: stringify ? JSON.stringify(body) : body,
    });
  }

  /**
   * Performs a PUT request.
   * @param {string} endpoint - The endpoint for the PUT request.
   * @param {Object} body - The body data to send with the PUT request.
   * @param {Object} [options={}] - Additional options for the PUT request.
   * @param {boolean} [stringify=true] - Whether to stringify the body.
   * @returns {Promise<Object>} - A promise resolving to the response data.
   */
  put(endpoint, body, options = {}, stringify = true) {
    return this.request(endpoint, {
      ...options,
      method: "PUT",
      body: stringify ? JSON.stringify(body) : body,
    });
  }

  /**
   * Performs a DELETE request.
   * @param {string} endpoint - The endpoint for the DELETE request.
   * @param {Object} [options={}] - Additional options for the DELETE request.
   * @returns {Promise<Object>} - A promise resolving to the response data.
   */
  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: "DELETE" });
  }

  /**
   * Performs a PATCH request.
   * @param {string} endpoint - The endpoint for the PATCH request.
   * @param {Object} body - The body data to send with the PATCH request.
   * @param {Object} [options={}] - Additional options for the PATCH request.
   * @param {boolean} [stringify=true] - Whether to stringify the body.
   * @returns {Promise<Object>} - A promise resolving to the response data.
   */
  patch(endpoint, body, options = {}, stringify = true) {
    return this.request(endpoint, {
      ...options,
      method: "PATCH",
      body: stringify ? JSON.stringify(body) : body,
    });
  }
}
