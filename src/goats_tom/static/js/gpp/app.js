/**
 * Top-level application class that bootstraps the GPP widget and initializes the API
 * with the CSRF token.
 *
 * @class
 */
class App {
  /**
   * Create the application and initialize dependencies.
   * @param {string} csrfToken - CSRF token for making secure API requests.
   */
  constructor(csrfToken) {
    window.api = new API("/api/", csrfToken);
    this.gpp = new GPP(document.getElementById("gppContainer"));
    this.gpp.init();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const token = document.body.dataset.csrfToken;
  new App(token);
});
