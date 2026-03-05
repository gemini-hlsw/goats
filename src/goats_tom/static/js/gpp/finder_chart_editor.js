/**
 * FinderChartEditor
 */
class FinderChartEditor {
  /** @type {HTMLElement} */
  #container;

  /** @type {HTMLElement} */
  #tableBox;

  /** @type {HTMLTableSectionElement} */
  #tbody;

  /** @type {Array<Object>} */
  #finderCharts;

  /** @type {string} */
  #idPrefix;

  /** @type {HTMLButtonElement} */
  #addButton;

  /** @type {HTMLElement|null} */
  #uploadForm = null;

  /** @type {{ onFinderChartUpload?: Function, onFinderChartCancel?: Function }} */
  #callbacks;

  /**
   * Map key is the current row id (temp id initially; may later be replaced).
   * Value: { controller, taskId }
   * @type {Map<string, { controller: AbortController, taskId: string | null }>}
   */
  #pendingUploads = new Map();

  #previewCache = new Map()
  constructor(
    parentElement,
    { data = [], idPrefix = "finder-charts", callbacks = {} } = {},
  ) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error(
        "FinderChartEditor expects an HTMLElement as the parent.",
      );
    }

    this.#callbacks = callbacks ?? {};
    this.#finderCharts = Array.isArray(data) ? [...data] : [];
    this.#idPrefix = idPrefix;

    this.#container = Utils.createElement("div", [
      "d-flex",
      "flex-column",
      "gap-3",
    ]);
    parentElement.appendChild(this.#container);

    this.#tableBox = Utils.createElement("div", ["table-responsive"]);
    this.#container.appendChild(this.#tableBox);

    this.#addButton = Utils.createElement("button", [
      "btn",
      "btn-outline-primary",
      "align-self-start",
    ]);
    this.#addButton.type = "button";
    this.#addButton.id = `${this.#idPrefix}-add`;
    this.#addButton.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;
    this.#addButton.addEventListener("click", () => this.#toggleUploadForm());

    this.render();
  }

  setData(data) {
    this.#finderCharts = Array.isArray(data) ? [...data] : [];
    this.render();
  }

  render() {
    this.#tableBox.innerHTML = "";
    this.#container.querySelector(".fc-empty-state")?.remove();
    this.#container.querySelector(".fc-separator")?.remove();

    if (!this.#finderCharts.length) {
      const empty = Utils.createElement("div", [
        "text-muted",
        "fc-empty-state",
      ]);
      empty.textContent = "No finder charts available.";
      this.#container.appendChild(empty);
    } else {
      const table = this.#buildTable();
      this.#tableBox.appendChild(table);
      for (const item of this.#finderCharts) {
        this.#tbody.appendChild(this.#row(item));
      }
    }

    this.#container.appendChild(
      Utils.createElement("hr", ["my-1", "fc-separator"]),
    );
    if (this.#uploadForm) {
        this.#container.appendChild(this.#uploadForm);
      }
      
    this.#container.appendChild(this.#addButton);
  }

  #buildTable() {
    const table = Utils.createElement("table", [
      "table",
      "table-borderless",
      "align-middle",
      "mb-0",
      "fs-6",
    ]);
    this.#tbody = document.createElement("tbody");
    table.appendChild(this.#tbody);
    return table;
  }

  #formatDate(value) {
    if (!value) return "-";
    const s = String(value);
    const isoLike = s.includes(" ") ? s.replace(" ", "T") : s;
    const d = new Date(isoLike);
    if (Number.isNaN(d.getTime())) return s;
    return d.toLocaleString();
  }

  #row(item) {
    const id = String(item.id ?? "");
    const tr = document.createElement("tr");
    tr.id = `${this.#idPrefix}-row-${id}`;
    tr.dataset.attachmentId = id;

    tr.appendChild(this.#cellFilename(item.fileName ?? "-"));
    tr.appendChild(this.#cellType(item.attachmentType ?? "-"));
    tr.appendChild(this.#cellText(item.description ?? "-"));
    tr.appendChild(this.#cellText(this.#formatDate(item.updatedAt)));
    tr.appendChild(this.#cellActions(item));

    return tr;
  }

  #cellFilename(filename) {
    const td = document.createElement("td");
    const wrap = Utils.createElement("div", [
      "d-flex",
      "align-items-center",
      "gap-2",
    ]);
    wrap.appendChild(
      Utils.createElement("i", ["fa-solid", "fa-file", "text-muted"]),
    );
    const name = Utils.createElement("span", ["fw-semibold"]);
    name.textContent = filename;
    wrap.appendChild(name);
    td.appendChild(wrap);
    return td;
  }

  #cellType(type) {
    const td = document.createElement("td");
    const badge = Utils.createElement("span", ["badge", "bg-success"]);
    badge.textContent = String(type).toUpperCase();
    td.appendChild(badge);
    return td;
  }

  #cellText(text) {
    const td = document.createElement("td");
    td.textContent = text ?? "-";
    return td;
  }

  #cellActions(item) {
    const id = String(item.id ?? "");
    const td = document.createElement("td");
    td.className = "text-end";

    const wrap = Utils.createElement("div", ["d-inline-flex", "gap-2"]);

    const downloadBtn = Utils.createElement("button", [
      "btn",
      "btn-sm",
      "btn-outline-primary",
    ]);
    downloadBtn.type = "button";
    downloadBtn.id = `${this.#idPrefix}-download-${id}`;

    const deleteBtn = Utils.createElement("button", [
      "btn",
      "btn-sm",
      "btn-outline-danger",
    ]);
    deleteBtn.type = "button";
    deleteBtn.id = `${this.#idPrefix}-delete-${id}`;
    deleteBtn.innerHTML = `<i class="fa-solid fa-trash"></i>`;
    deleteBtn.addEventListener("click", async () => {
      const tr = deleteBtn.closest("tr");
      if (!tr || tr.dataset.locked === "1") return;

      this.#lockRow(tr, deleteBtn);

      try {
        const res = await this.#callbacks.onFinderChartDelete?.({ id });
        const deletedId = String(res?.id ?? id);

        this.#removeById(deletedId);
      } catch (err) {
        this.#unlockRow(tr, deleteBtn);
        console.error("FinderChartEditor delete error:", err);
      }
    });

    if (item.status === "uploading") {
      downloadBtn.disabled = true;
      deleteBtn.disabled = true;
      downloadBtn.innerHTML = `<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>`;
      wrap.appendChild(downloadBtn);
      wrap.appendChild(deleteBtn);
      td.appendChild(wrap);
      return td;
    }

    downloadBtn.innerHTML = `<i class="fa-solid fa-download"></i>`;
    downloadBtn.addEventListener("click", async () => {
      try {
        const res = await this.#callbacks.onFinderChartDownload?.({ attachmentId: id });
        const url = res?.url;
        if (!url) throw new Error("Missing url from download callback.");
    
        const a = document.createElement("a");
        a.href = url;
        document.body.appendChild(a);
        a.click();
        a.remove();
      } catch (err) {
        console.error("FinderChartEditor download error:", err);
      }
    });
    
    const previewBtn = Utils.createElement("button", [
      "btn",
      "btn-sm",
      "btn-outline-secondary",
    ]);
    
    previewBtn.type = "button";
    previewBtn.innerHTML = `<i class="fa-solid fa-eye"></i>`;
    
    previewBtn.addEventListener("click", async () => {
      try {
        const res = await this.#callbacks.onFinderChartDownload?.({
          attachmentId: id,
        });
    
        const url = res?.url;
        if (!url) throw new Error("Missing url for preview.");
    
        this.#showPreview(url);
    
      } catch (err) {
        console.error("Preview error:", err);
      }
    });
    wrap.appendChild(previewBtn);
    wrap.appendChild(downloadBtn);
    wrap.appendChild(deleteBtn);
    td.appendChild(wrap);
    return td;
  }

  #removeById(id) {
    this.#finderCharts = this.#finderCharts.filter(
      (fc) => String(fc.id) !== String(id),
    );
    this.render();
  }

  /**
   * Replace temp id with real attachment id.
   * @param {string} tempId
   * @param {string|number} newId
   */
  #finalizeUploadId(tempId, newId) {
    const oldId = String(tempId);
    const realId = String(newId);

    this.#finderCharts = this.#finderCharts.map((fc) => {
      if (String(fc.id) !== oldId) return fc;
      return {
        ...fc,
        id: realId,
        status: undefined,
        updatedAt: new Date().toISOString(),
      };
    });

    // Move pending upload entry to the new key if needed.
    const pending = this.#pendingUploads.get(oldId);
    if (pending) {
      this.#pendingUploads.delete(oldId);
      this.#pendingUploads.set(realId, pending);
    }

    this.render();
  }

  #buildUploadForm() {
    const wrap = Utils.createElement("div", ["bg-body", "rounded-2"]);
    wrap.id = `${this.#idPrefix}-upload-form`;

    const form = Utils.createElement("form", [
      "d-flex",
      "flex-column",
      "gap-3",
    ]);

    // File input group
    const fileGroup = Utils.createElement("div", []);
    const fileId = `${this.#idPrefix}-file`;

    const fileLabel = Utils.createElement("label", ["form-label"]);
    fileLabel.htmlFor = fileId;
    fileLabel.textContent = "Select finder chart";

    const fileInput = Utils.createElement("input", ["form-control"]);
    fileInput.id = fileId;
    fileInput.type = "file";
    fileInput.name = "file";

    fileGroup.appendChild(fileLabel);
    fileGroup.appendChild(fileInput);

    // Description group
    const descGroup = Utils.createElement("div", []);
    const descId = `${this.#idPrefix}-description`;

    const descLabel = Utils.createElement("label", ["form-label"]);
    descLabel.htmlFor = descId;
    descLabel.textContent = "Description";

    const descInput = Utils.createElement("input", ["form-control"]);
    descInput.id = descId;
    descInput.type = "text";
    descInput.name = "description";
    descInput.placeholder = "Optional";

    descGroup.appendChild(descLabel);
    descGroup.appendChild(descInput);

    // Buttons
    const buttons = Utils.createElement("div", ["d-flex", "gap-2"]);

    const upload = Utils.createElement("button", ["btn", "btn-primary"]);
    upload.type = "button";
    upload.textContent = "Upload";

    const cancel = Utils.createElement("button", ["btn", "btn-secondary"]);
    cancel.type = "button";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => this.#toggleUploadForm());

    upload.addEventListener("click", async () => {
      const file = fileInput.files?.[0] ?? null;
      if (!file) {
        fileInput.focus();
        return;
      }

      upload.disabled = true;

      const tempId = `temp-${Date.now()}`;

      const tempItem = {
        id: tempId,
        fileName: file.name,
        attachmentType: "FINDER",
        fileSize: file.size ?? null,
        description: descInput.value?.trim() || null,
        updatedAt: new Date().toISOString(),
        status: "uploading",
      };

      this.#finderCharts = [...this.#finderCharts, tempItem];
      this.render();

      const controller = new AbortController();
      this.#pendingUploads.set(String(tempId), { controller, taskId: null });

      try {
        if (!this.#callbacks.onFinderChartUpload) {
          throw new Error("Missing callback: onFinderChartUpload");
        }

        const result = await this.#callbacks.onFinderChartUpload({
          file,
          description: tempItem.description ?? "",
          signal: controller.signal,
          onTaskId: (taskId) => {
            const pending = this.#pendingUploads.get(String(tempId));
            if (pending) pending.taskId = String(taskId);
          },
        });

        const attachmentId = result?.data?.id ?? null;

        if (!attachmentId) {
          console.log("Upload result:", result);
          throw new Error("Upload did not return an attachment id.");
        }

        this.#finalizeUploadId(tempId, attachmentId);
        fileInput.value = "";
        descInput.value = "";
      } catch (err) {
        this.#removeById(tempId);
        console.error("FinderChartEditor upload error:", err);
      } finally {
        this.#pendingUploads.delete(String(tempId));
        upload.disabled = false;
      }
    });

    buttons.appendChild(upload);
    buttons.appendChild(cancel);

    form.appendChild(fileGroup);
    form.appendChild(descGroup);
    form.appendChild(buttons);

    wrap.appendChild(form);
    return wrap;
  }

  #toggleUploadForm() {
    if (this.#uploadForm) {
      this.#uploadForm.remove();
      this.#uploadForm = null;
      this.#addButton.classList.remove("d-none");
      return;
    }
    this.#addButton.classList.add("d-none");
    this.#uploadForm = this.#buildUploadForm();
    this.render();
  }
  #lockRow(tr, deleteBtn) {
    if (!tr) return;

    tr.dataset.locked = "1";
    tr.style.opacity = "0.55";
    tr.style.pointerEvents = "none";

    tr.querySelectorAll("button").forEach((b) => {
      b.disabled = true;
    });

    if (deleteBtn) {
      deleteBtn.dataset.originalHtml = deleteBtn.innerHTML;
      deleteBtn.innerHTML = `<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>`;
    }
  }

  #unlockRow(tr, deleteBtn) {
    if (!tr) return;

    delete tr.dataset.locked;
    tr.style.opacity = "";
    tr.style.pointerEvents = "";

    tr.querySelectorAll("button").forEach((b) => {
      b.disabled = false;
    });

    if (deleteBtn && deleteBtn.dataset.originalHtml) {
      deleteBtn.innerHTML = deleteBtn.dataset.originalHtml;
      delete deleteBtn.dataset.originalHtml;
    }
  }
  
  #showPreview(url) {
    let modal = document.getElementById("fc-preview-modal");
  
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "fc-preview-modal";
      modal.className = "modal fade";
      modal.innerHTML = `
        <div class="modal-dialog modal-lg modal-dialog-centered">
          <div class="modal-content">
  
            <div class="modal-header">
              <h5 class="modal-title">Finder Chart Preview</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
  
            <div class="modal-body text-center">
              <img id="fc-preview-img" style="max-width:100%; max-height:70vh;">
            </div>
  
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }
  
    const img = modal.querySelector("#fc-preview-img");
    img.src = url;
  
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
  }
}
