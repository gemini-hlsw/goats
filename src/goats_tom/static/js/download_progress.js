/**
 * Updates the download link in the navbar to reflect the number of active downloads.
 *
 * This function modifies the text content of the download badge element based on
 * the number of active downloads. If there are active downloads, the badge is
 * made visible and updated with the count. If there are no active downloads,
 * the badge is hidden.
 *
 * @param {number} activeDownloads - The number of active downloads.
 */
const updateNavbarDownloadLink = (activeDownloads) => {
  // Get the download badge element from the DOM
  const downloadBadge = document.getElementById("downloadBadge");
  const noDownloadsMessage = document.getElementById("noDownloadsMessage");

  // Check if there are any active downloads
  if (activeDownloads > 0) {
    downloadBadge.textContent = activeDownloads;
    downloadBadge.classList.remove("d-none");
    noDownloadsMessage.classList.add("d-none");
  } else {
    // Hide the badge by adding "d-none" class
    downloadBadge.classList.add("d-none");
    noDownloadsMessage.classList.remove("d-none");
  }
};

/**
 * Updates or creates a new download progress item in the DOM.
 * If the item does not exist, it creates a new element with progress information.
 * If the item exists, it updates the existing element's details.
 * Newly created items are prepended to the container and removed after some seconds.
 *
 * @param {Object} downloadProgress - The download progress information.
 */
const sanitizeDomId = (value) => String(value || "").replace(/[^A-Za-z0-9\-_:.]/g, "_");

const updateDownloadProgress = (downloadProgress) => {
  const container = document.getElementById("downloadTasksBanner");
  const safeUniqueId = sanitizeDomId(downloadProgress.unique_id);
  let downloadItem = document.getElementById(safeUniqueId);

  // If the item doesn't exist, create it.
  if (!downloadItem) {
    downloadItem = document.createElement("div");
    downloadItem.setAttribute("id", safeUniqueId);
    downloadItem.setAttribute("class", "row align-items-center");

    const iconCol = document.createElement("div");
    iconCol.className = "col-auto";
    const icon = document.createElement("i");
    icon.className = "fa-solid fa-file-arrow-down fa-2xl text-light";
    iconCol.appendChild(icon);

    const contentCol = document.createElement("div");
    contentCol.className = "col";

    const labelP = document.createElement("p");
    labelP.className = "fw-bold text-muted mb-0";
    labelP.textContent = downloadProgress.label || "";

    const progress = document.createElement("div");
    progress.className = "progress";
    progress.setAttribute("aria-label", "Downloading");
    progress.setAttribute("aria-valuenow", "100");
    progress.setAttribute("aria-valuemin", "0");
    progress.setAttribute("aria-valuemax", "100");
    progress.setAttribute("role", "status");

    const progressBar = document.createElement("div");
    progressBar.id = `${safeUniqueId}-progressBar`;
    progressBar.className = "progress-bar placeholder-wave text-bg-primary";
    progressBar.style.width = "100%";
    progress.appendChild(progressBar);

    const row = document.createElement("div");
    row.className = "row justify-content-between";

    const downloadedCol = document.createElement("div");
    downloadedCol.className = "col-auto";
    const downloadedBytesSmall = document.createElement("small");
    downloadedBytesSmall.id = `${safeUniqueId}-downloadedBytes`;
    downloadedBytesSmall.textContent = downloadProgress.downloaded_bytes || "";
    downloadedCol.appendChild(downloadedBytesSmall);

    const statusCol = document.createElement("div");
    statusCol.className = "col-auto";
    const statusSmall = document.createElement("small");
    statusSmall.id = `${safeUniqueId}-status`;
    statusSmall.textContent = downloadProgress.status || "";
    statusCol.appendChild(statusSmall);

    row.appendChild(downloadedCol);
    row.appendChild(statusCol);

    contentCol.appendChild(labelP);
    contentCol.appendChild(progress);
    contentCol.appendChild(row);

    const divider = document.createElement("div");
    divider.className = "dropdown-divider";

    downloadItem.appendChild(iconCol);
    downloadItem.appendChild(contentCol);
    downloadItem.appendChild(divider);

    container.prepend(downloadItem);
  } else {
    // If the item exists, update its details.
    const downloadedBytesSmall = document.getElementById(
      `${safeUniqueId}-downloadedBytes`
    );
    downloadedBytesSmall.textContent = downloadProgress.downloaded_bytes || "";
    const statusSmall = document.getElementById(`${safeUniqueId}-status`);
    if (downloadProgress.status !== null) {
      statusSmall.textContent = downloadProgress.status;
    }

    // Update the progress bar if done.
    if (downloadProgress.error) {
      const progressBarDiv = document.getElementById(
        `${safeUniqueId}-progressBar`
      );
      progressBarDiv.classList.replace("text-bg-primary", "text-bg-danger");
      progressBarDiv.classList.remove("placeholder-wave");

      // Remove after 5 seconds.
      setTimeout(() => {
        downloadItem.remove();
      }, 5000);
    } else if (downloadProgress.done) {
      const progressBarDiv = document.getElementById(
        `${safeUniqueId}-progressBar`
      );
      progressBarDiv.classList.replace("text-bg-primary", "text-bg-secondary");
      progressBarDiv.classList.remove("placeholder-wave");

      // Remove after 5 seconds.
      setTimeout(() => {
        downloadItem.remove();
      }, 5000);
    }
  }
};

/**
 * Asynchronously fetches ongoing tasks from the server.
 *
 * This function makes an HTTP GET request to the "/api/ongoing-tasks/" endpoint
 * to retrieve a list of ongoing tasks. If the request is successful, it updates
 * the tasks banner with the fetched data.
 */
const fetchOngoingTasks = async () => {
  try {
    // Fetch ongoing tasks data from the server
    const response = await fetch("/api/ongoing-tasks/");

    // Check if the HTTP request was successful
    if (!response.ok) {
      // If not successful, throw an error with the status code
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    // Parse the JSON response to get tasks data
    const tasks = await response.json();
    updateDownloadTasksBanner(tasks);
  } catch (error) {
    // Log any errors to the console
    console.error("Error:", error);
  }
};

// Start the polling when the page loads
// document.addEventListener("DOMContentLoaded", fetchOngoingTasks);