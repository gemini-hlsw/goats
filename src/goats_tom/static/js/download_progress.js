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
const updateDownloadProgress = (downloadProgress) => {
  const container = document.getElementById("downloadTasksBanner");
  let downloadItem = document.getElementById(downloadProgress.unique_id);

  // If the item doesn't exist, create it.
  if (!downloadItem) {
    downloadItem = document.createElement("div");
    downloadItem.setAttribute("id", downloadProgress.unique_id);
    downloadItem.setAttribute("class", "row align-items-center");
    downloadItem.innerHTML = `
      <div class="col-auto">
        <i class="fa-solid fa-file-arrow-down fa-2xl text-light"></i>
      </div>
      <div class="col">
        <p class="fw-bold text-muted mb-0">${downloadProgress.label}</p>
        <div class="progress" aria-label="Downloading" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100" role="status">
          <div id="${downloadProgress.unique_id}-progressBar" class="progress-bar placeholder-wave text-bg-primary" style="width: 100%"></div>
        </div>
        <div class="row justify-content-between">
          <div class="col-auto">
            <small id="${downloadProgress.unique_id}-downloadedBytes">${downloadProgress.downloaded_bytes}</small>
          </div>
          <div class="col-auto">
            <small id="${downloadProgress.unique_id}-status">${downloadProgress.status}</small>
          </div>
        </div>
      </div>
      <div class="dropdown-divider"></div>
    `;
    container.prepend(downloadItem);
  } else {
    // If the item exists, update its details.
    const downloadedBytesSmall = document.getElementById(
      `${downloadProgress.unique_id}-downloadedBytes`
    );
    downloadedBytesSmall.textContent = downloadProgress.downloaded_bytes || "";
    const statusSmall = document.getElementById(`${downloadProgress.unique_id}-status`);
    if (downloadProgress.status !== null) {
      statusSmall.textContent = downloadProgress.status;
    }

    // Update the progress bar if done.
    if (downloadProgress.error) {
      const progressBarDiv = document.getElementById(
        `${downloadProgress.unique_id}-progressBar`
      );
      progressBarDiv.classList.replace("text-bg-primary", "text-bg-danger");
      progressBarDiv.classList.remove("placeholder-wave");

      // Remove after 5 seconds.
      setTimeout(() => {
        downloadItem.remove();
      }, 5000);
    } else if (downloadProgress.done) {
      const progressBarDiv = document.getElementById(
        `${downloadProgress.unique_id}-progressBar`
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