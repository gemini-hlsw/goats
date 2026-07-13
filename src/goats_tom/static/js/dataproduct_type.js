/**
 * Handles the editable data product type dropdowns rendered by the
 * `dataproduct_type_dropdown` template tag.
 *
 * Uses event delegation on the document so a single listener covers every
 * dropdown on the page, regardless of which table it lives in. Requires
 * `getCsrfToken()` (js/get_csrf_token.js) and `window.toast`
 * (js/toast_manager.js), both loaded globally in the base template.
 */
(() => {
  // Guard against running twice if the script is included more than once.
  if (window.dataproductTypeDropdownInitialized) return;
  window.dataproductTypeDropdownInitialized = true;

  /**
   * Updates the `data_product_type` of a data product.
   * @param {string} id - The unique identifier of the data product.
   * @param {string} dataProductType - The new data product type.
   * @returns {Promise<void>} - Resolves when the request is completed.
   */
  const updateDataProductType = async (id, dataProductType) => {
    const url = `/api/dataproducttype/${id}/`;

    const response = await fetch(url, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ data_product_type: dataProductType }),
    });
    if (!response.ok) {
      // The error response may not be JSON (e.g. an HTML error page).
      const data = await response.json().catch(() => null);
      throw new Error(
        data?.data_product_type?.[0] || "Failed to update data product type."
      );
    }
  };

  /**
   * Runs the photometry processor on a data product, generating its
   * `ReducedDatum` points immediately instead of waiting for a manual
   * "Plot" click in the Photometry tab.
   * @param {string} id - The unique identifier of the data product.
   * @returns {Promise<void>} - Resolves when the request is completed.
   */
  const runPhotometryProcessor = async (id) => {
    const url = `/api/runprocessor/`;

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      credentials: "same-origin",
      body: JSON.stringify({ data_product: id, data_product_type: "photometry" }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.detail || "Failed to process photometry data.");
    }
  };

  document.addEventListener("click", async (event) => {
    const item = event.target.closest(
      ".dataproduct-type-dropdown a.dropdown-item[data-value]"
    );

    if (!item) return;
    event.preventDefault();

    const dropdown = item.closest(".dataproduct-type-dropdown");
    const { id } = dropdown.dataset;
    const { value } = item.dataset;

    const mainButton = dropdown.querySelector(".btn-secondary");
    const buttonText = mainButton.querySelector(".button-text");
    const spinner = mainButton.querySelector(".spinner-border");

    buttonText.classList.add("d-none");
    spinner.classList.remove("d-none");
    mainButton.disabled = true;

    try {
      await updateDataProductType(id, value);

      if (value === "photometry") {
        try {
          await runPhotometryProcessor(id);
        } catch (error) {
          // Best-effort: the retag already succeeded, so don't block the
          // reload on a processing failure (e.g. an unsupported file).
          console.error(error);
        }
      }

      // Reload so every part of the page that depends on data product type
      // (photometry/spectroscopy plots, sharing table, recent photometry)
      // picks up the change from a fresh server render.
      window.location.reload();
    } catch (error) {
      window.toast?.show({
        label: "Failed to Update Data Product Type",
        message: error.message,
        color: "danger",
      });
    } finally {
      buttonText.classList.remove("d-none");
      spinner.classList.add("d-none");
      mainButton.disabled = false;
    }
  });
})();
