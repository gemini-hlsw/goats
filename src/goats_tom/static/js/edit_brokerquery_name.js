/**
 * Initializes event listeners for in-place editing icons.
 *
 * This function attaches click event listeners to the containers of edit, save,
 * and cancel icons. It ensures that these listeners remain effective even after
 * Font Awesome replaces the inner `i` elements with `svg` elements.
 */
const initializeIconListeners = () => {
  const table = document.getElementById("queryTable"); // Assuming the table has this ID

  table.addEventListener("click", event => {
    const container = event.target.closest("span");
    if (!container) return;

    const parentTd = container.closest("td");
    if (container.classList.contains("edit-container")) {
      enterEditMode(parentTd);
    } else if (container.classList.contains("save-container")) {
      saveChanges(parentTd);
    } else if (container.classList.contains("cancel-container")) {
      cancelEdit(parentTd);
    }
  });
};

/**
 * Enters edit mode for a specific query row.
 *
 * @param {HTMLElement} container - The container element for the edit icon.
 */
const enterEditMode = (container) => {
  let parentTd = container.closest("td");
  toggleEditElements(parentTd, true);
  let queryNameSpan = parentTd.querySelector(".query-name")
  let queryNameAnchor = parentTd.querySelector(".query-name a");
  let currentName = queryNameAnchor.textContent;

  let inputElement = document.createElement("input");
  inputElement.type = "text";
  inputElement.className = "form-control edit-input me-1";
  inputElement.style.display = "inline-block";
  inputElement.style.width = "auto";
  inputElement.value = currentName;

  queryNameAnchor.style.display = "none"; // Hide the anchor tag
  queryNameSpan.after(inputElement); // Insert the input next to the anchor tag
};

/**
 * Saves the changes made to the query name and updates the server asynchronously.
 *
 * @param {HTMLElement} container - The container element for the save icon.
 */
const saveChanges = async (container) => {
  let parentTd = container.closest("td");
  let newName = parentTd.querySelector(".edit-input").value;
  let queryId = parentTd.querySelector(".query-name").dataset.id;

  try {
    const response = await fetch(`/alerts/query/${queryId}/update-name`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": getCsrfToken()
      },
      body: `name=${encodeURIComponent(newName)}`
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log("Success:", data);
    // Update link text instead of replacing the entire link
    let queryNameAnchor = parentTd.querySelector(".query-name a");
    queryNameAnchor.textContent = newName;
    queryNameAnchor.style.display = ""; // Show the anchor tag again
  } catch (error) {
    console.error("Error:", error);
  } finally {
    toggleEditElements(parentTd, false);
    parentTd.querySelector(".edit-input").remove();
  }
};

/**
 * Cancels the edit operation and reverts any changes.
 *
 * @param {HTMLElement} container - The container element for the cancel icon.
 */
const cancelEdit = (container) => {
  let parentTd = container.closest("td");
  toggleEditElements(parentTd, false);
  let queryNameAnchor = parentTd.querySelector(".query-name a");
  queryNameAnchor.style.display = ""; // Show the anchor tag again

  let inputElement = parentTd.querySelector(".edit-input");
  if (inputElement) {
    inputElement.remove();
  }
};

/**
 * Toggles the visibility of edit-related elements in the table row.
 *
 * @param {HTMLElement} parentTd - The parent TD element containing the icons.
 * @param {boolean} isEditing - Flag indicating whether edit mode is active.
 */
const toggleEditElements = (parentTd, isEditing) => {
  parentTd.querySelector(".query-name").style.display = isEditing ? "none" : "";
  parentTd.querySelector(".edit-container").style.display = isEditing ? "none" : "";
  parentTd.querySelector(".save-container").style.display = isEditing ? "inline" : "none";
  parentTd.querySelector(".cancel-container").style.display = isEditing ? "inline" : "none";
};

// Initialize the event listeners when the DOM is fully loaded.
document.addEventListener("DOMContentLoaded", initializeIconListeners);
