/**
 * Shows the number of active downloads on the navbar icon, as the bell does.
 *
 * @param {number} activeDownloads - The number of active downloads.
 */
const updateNavbarDownloadLink = (activeDownloads) => {
  const downloadBadge = document.getElementById("downloadBadge");
  if (!downloadBadge) return;

  downloadBadge.textContent = activeDownloads > 9 ? "9+" : activeDownloads;
  downloadBadge.classList.toggle("d-none", activeDownloads === 0);
};

/**
 * Shows the empty message while the downloads panel has no rows.
 */
const updateDownloadsEmpty = () => {
  const container = document.getElementById("downloadTasksBanner");
  const empty = document.getElementById("noDownloadsMessage");
  if (!container || !empty) return;

  empty.classList.toggle("d-none", container.childElementCount > 0);
};

/** Downloads still running, as seen through the WebSocket. */
const activeDownloadIds = new Set();

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

  if (downloadProgress.done || downloadProgress.error) {
    activeDownloadIds.delete(safeUniqueId);
  } else {
    activeDownloadIds.add(safeUniqueId);
  }
  updateNavbarDownloadLink(activeDownloadIds.size);

  // If the item doesn't exist, create it.
  if (!downloadItem) {
    downloadItem = document.createElement("div");
    downloadItem.setAttribute("id", safeUniqueId);
    downloadItem.className = "download-row";

    const kind = document.createElement("span");
    kind.className = "download-kind kind-info";
    kind.setAttribute("aria-hidden", "true");
    const icon = document.createElement("i");
    icon.className = "fa-solid fa-file-arrow-down";
    kind.appendChild(icon);

    const body = document.createElement("div");
    body.className = "download-body";

    const title = document.createElement("div");
    title.className = "download-title";
    title.textContent = downloadProgress.label || "";

    const progress = document.createElement("div");
    progress.className = "progress download-progress";
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

    const meta = document.createElement("div");
    meta.className = "download-meta";

    const downloadedBytesSmall = document.createElement("span");
    downloadedBytesSmall.id = `${safeUniqueId}-downloadedBytes`;
    downloadedBytesSmall.textContent = downloadProgress.downloaded_bytes || "";

    const statusSmall = document.createElement("span");
    statusSmall.id = `${safeUniqueId}-status`;
    statusSmall.textContent = downloadProgress.status || "";

    meta.appendChild(downloadedBytesSmall);
    meta.appendChild(statusSmall);

    body.appendChild(title);
    body.appendChild(progress);
    body.appendChild(meta);

    downloadItem.appendChild(kind);
    downloadItem.appendChild(body);

    container.prepend(downloadItem);
    updateDownloadsEmpty();
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
        updateDownloadsEmpty();
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
        updateDownloadsEmpty();
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