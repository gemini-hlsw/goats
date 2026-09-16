/**
 * Manages the behavior and display of a offcanvas component for showing help information.
 */
class HelpOffcanvas {
  /**
   * Constructs a HelpOffcanvas instance attached to a specified parent element.
   * @param {HTMLElement} parentElement The container where the offcanvas will be appended.
   */
  constructor(parentElement) {
    this.parentElement = parentElement;
    this.id = "helpOffcanvas";
    this.titleElement = null;
    this.loadingElement = null;
    this.contentElement = null;
    this.offcanvas = this._createOffcanvas();
    this.parentElement.appendChild(this.offcanvas);
    this.bsOffcanvas = new bootstrap.Offcanvas(this.offcanvas);
    this.primitiveHelpHtml = `
      <ul>
        <li><strong>Adding Primitives:</strong> Insert <code>p.primitive_name(optional_arguments)</code> at the required position in the recipe.</li>
        <li><strong>Modify Parameters:</strong> Change the arguments of any primitive to meet your specific requirements. E.g., <code>p.prepare(suffix="_test", require_wcs=True)</code></li>
        <li><strong>Interactive Mode:</strong> Note that the following primitives have the argument <code>interactive</code>:
        <ul>
          <li><code>calculateSensitivity</code></li>
          <li><code>determineWavelengthSolution</code></li>
          <li><code>findApertures</code></li>
          <li><code>normalizeFlat</code></li>
          <li><code>skyCorrectFromSlit</code></li>
          <li><code>traceApertures</code></li>
        </ul>
        If you want to turn on the interactive tools of DRAGONS, make sure to set the interactive parameter for these primitives whenever present in the recipe; e.g., <code>p.determineWavelengthSolution(interactive=True)</code></li>
        <li><strong>Reorder Primitives:</strong> Move the primitives to different positions to change the execution order.</li>
        <li><strong>Remove Primitives:</strong> Delete the entire primitive line to remove from the recipe.</li>
      </ul>
      <p>A list of all available primitives and parameters for this observation type are below</p>
    `;
  }

  /**
   * Creates the offcanvas HTML structure and returns the element.
   * @private
   * @returns {HTMLElement} The fully constructed offcanvas element.
   */
  _createOffcanvas() {
    const offcanvas = Utils.createElement("div", ["offcanvas", "offcanvas-end"]);
    offcanvas.setAttribute("data-bs-scroll", "true");
    offcanvas.setAttribute("data-bs-backdrop", "false");
    offcanvas.setAttribute("tabindex", "-1");
    offcanvas.setAttribute("aria-labelledby", `${this.id}Title`);
    offcanvas.id = this.id;

    const header = Utils.createElement("div", "offcanvas-header");
    const title = Utils.createElement("h5", "offcanvas-title");
    title.id = `${this.id}Title`;
    this.titleElement = title; // Store reference to title element.

    const closeButton = Utils.createElement("button", ["btn", "btn-close"]);
    closeButton.setAttribute("type", "button");
    closeButton.setAttribute("data-bs-dismiss", "offcanvas");
    closeButton.setAttribute("aria-label", "Close");

    const body = Utils.createElement("div", ["offcanvas-body", "pt-0"]);
    const helpContentDiv = Utils.createElement("div");
    this.contentElement = helpContentDiv; // Store reference to content element.

    const loadingDiv = Utils.createElement("div", ["d-flex", "justify-content-center"]);
    const spinner = Utils.createElement("div", "spinner-border");
    spinner.setAttribute("role", "status");
    const sr = Utils.createElement("span", "visually-hidden");
    sr.textContent = "Loading...";
    loadingDiv.appendChild(spinner);
    loadingDiv.appendChild(sr);
    this.loadingElement = loadingDiv; // Store reference to loading element.

    body.appendChild(helpContentDiv);
    body.appendChild(loadingDiv);

    header.appendChild(title);
    header.appendChild(closeButton);
    offcanvas.appendChild(header);
    offcanvas.appendChild(body);

    return offcanvas;
  }

  /**
   * Sets the title of the offcanvas.
   * @param {string} text The text to set as the offcanvas title.
   */
  setTitle(text) {
    this.titleElement.textContent = text;
  }

  /**
   * Shows the content of the offcanvas, hiding the loading indicator.
   */
  showContent() {
    this.loadingElement.classList.add("d-none");
    this.contentElement.classList.remove("d-none");
  }

  /**
   * Shows the loading indicator and hides the content.
   */
  isLoading() {
    this.contentElement.classList.add("d-none");
    this.loadingElement.classList.remove("d-none");
  }

  /**
   * Displays the offcanvas.
   */
  show() {
    this.bsOffcanvas.show();
  }

  /**
   * Hides the offcanvas.
   */
  hide() {
    this.bsOffcanvas.hide();
  }

  /**
   * Clears the title and content of the offcanvas.
   */
  clearTitleAndContent() {
    this.titleElement.textContent = "";
    this.contentElement.innerHTML = "";
  }

  /**
   * Updates and shows the primitives documentation.
   * @param {Object} recipe The recipe object containing all documentation info, including file
   * type and help details for each primitive.
   */
  updateAndShowPrimitivesDocumentation(recipe) {
    this.setTitle(
      `${Utils.formatDisplayText(recipe.observation_type)} Primitives Documentation`
    );
    const primitivesDocumentation = this._renderPrimitivesDocumentation(recipe);
    this.contentElement.appendChild(primitivesDocumentation);
    this.showContent();
  }

  /**
   * Builds and renders an accordion in the offcanvas body displaying documentation for available
   * primitives based on the given recipe.
   * @private
   * @param {Object} recipe The recipe object containing all documentation info, including file
   * type and help details for each primitive.
   * @returns {HTMLElement} A container element with the constructed accordion and introductory
   * paragraph.
   */
  _renderPrimitivesDocumentation(recipe) {
    // Build paragraph.
    const container = Utils.createElement("div");
    const about = Utils.createElement("p");
    about.innerHTML = this.primitiveHelpHtml;

    const accordionId = `${this.id}Accordion`;
    const accordion = Utils.createElement("div", ["accordion", "accordion-flush"]);
    accordion.id = accordionId;

    // Loop through and build the accordion item and docs.
    Object.entries(recipe.help).forEach(([key, value], index) => {
      const item = Utils.createElement("div", ["accordion-item"]);
      const header = Utils.createElement("h2", ["accordion-header"]);
      const buttonId = `${accordionId}-heading-${index}`;
      const collapseId = `${accordionId}-collapse-${index}`;

      const button = Utils.createElement("button", ["accordion-button", "collapsed"]);
      button.setAttribute("type", "button");
      button.setAttribute("data-bs-toggle", "collapse");
      button.setAttribute("data-bs-target", `#${collapseId}`);
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-controls", collapseId);
      button.textContent = key;

      const collapseDiv = Utils.createElement("div", [
        "accordion-collapse",
        "collapse",
      ]);
      collapseDiv.setAttribute("id", collapseId);
      collapseDiv.setAttribute("aria-labelledby", buttonId);
      collapseDiv.setAttribute("data-bs-parent", `#${accordionId}`);

      const bodyDiv = Utils.createElement("div", ["accordion-body"]);

      // Params Section.
      if (value.params) {
        const paramsTitle = Utils.createElement("h6", [
          "bg-light-subtle",
          "py-1",
          "px-2",
        ]);
        paramsTitle.textContent = "Parameters";
        bodyDiv.appendChild(paramsTitle);

        const paramsList = Utils.createElement("ul", "list-unstyled");
        Object.entries(value.params).forEach(([paramKey, paramDetails]) => {
          const li = Utils.createElement("li", "mb-2");

          // Create the parameter name and value.
          const paramNameValue = Utils.createElement("p", ["d-inline", "fw-bold"]);

          // Span for parameter name.
          const paramNameSpan = Utils.createElement("span");
          paramNameSpan.textContent = `${paramKey}=`;
          paramNameValue.appendChild(paramNameSpan);

          // Span for parameter value, italics and normal weight.
          const paramValueSpan = Utils.createElement("span", [
            "fst-italic",
            "fw-normal",
          ]);
          paramValueSpan.textContent = paramDetails.value;

          paramNameValue.appendChild(paramValueSpan);
          li.appendChild(paramNameValue);

          // Create documentation text below the parameter name and value.
          if (paramDetails.doc) {
            const paramDoc = Utils.createElement("pre", ["ms-3"]);
            paramDoc.textContent = paramDetails.doc;
            li.appendChild(paramDoc);
          }

          paramsList.appendChild(li);
        });
        bodyDiv.appendChild(paramsList);
      }

      // Docstring section.
      if (value.docstring) {
        Object.entries(value.docstring).forEach(([docKey, docValue]) => {
          if (
            ((Array.isArray(docValue) && docValue.length > 0) ||
              (typeof docValue === "string" && docValue !== "")) &&
            !["parameters", "returns"].includes(docKey)
          ) {
            const docTitle = Utils.createElement("h6", [
              "bg-light-subtle",
              "py-1",
              "px-2",
            ]);
            docTitle.textContent = Utils.formatDisplayText(docKey);
            bodyDiv.appendChild(docTitle);

            const docContent = Utils.createElement("pre");
            docContent.textContent = Array.isArray(docValue)
              ? docValue.join("\n")
              : docValue;
            bodyDiv.appendChild(docContent);
          }
        });
      }

      // Append all to build element.
      header.appendChild(button);
      collapseDiv.appendChild(bodyDiv);
      item.append(header, collapseDiv);
      accordion.appendChild(item);
    });
    container.append(about, accordion);
    return container;
  }
}
