class FinderChartEditor {
  /** @type {HTMLElement} */
  #container;

  /** @type {HTMLElement} */
  #tableBox;

  /** @type {HTMLTableSectionElement|null} */
  #tbody = null;

  /** @type {string} */
  #idPrefix;

  /** @type {HTMLButtonElement} */
  #addButton;

  /** @type {HTMLElement|null} */
  #addForm = null;

  /**
   * Base items loaded from backend.
   * @type {Array<Object>}
   */
  #baseItems = [];

  /**
   * Locally staged new items.
   * @type {Array<Object>}
   */
  #stagedAdds = [];

  /**
   * Backend item ids staged for delete.
   * @type {Set<string>}
   */
  #stagedDeletes = new Set();

  /**
   * @type {{
   *   onFinderChartDownload?: Function,
   *   onChange?: Function
   * }}
   */
  #callbacks;

  /**
   * Create a new finder chart editor.
   *
   * @param {HTMLElement} parentElement
   *   Container element where the editor will be rendered.
   * @param {Object} [options={}]
   *   Editor configuration options.
   * @param {Array<Object>} [options.data=[]]
   *   Initial finder chart data loaded from the backend.
   * @param {string} [options.idPrefix="finder-charts"]
   *   Prefix used for generated element ids.
   * @param {Object} [options.callbacks={}]
   *   Optional editor callbacks.
   */
  constructor(
    parentElement,
    { data = [], idPrefix = "finder-charts", callbacks = {} } = {},
  ) {
    if (!(parentElement instanceof HTMLElement)) {
      throw new Error("FinderChartEditor expects an HTMLElement.");
    }

    this.#callbacks = callbacks ?? {};
    this.#baseItems = Array.isArray(data) ? [...data] : [];
    this.#idPrefix = idPrefix;

    this.#container = Utils.createElement("div", [
      "d-flex",
      "flex-column",
      "gap-3",
    ]);
    parentElement.appendChild(this.#container);

    this.#tableBox = Utils.createElement("div", ["table-responsive"]);

    this.#addButton = Utils.createElement("button", [
      "btn",
      "btn-outline-primary",
    ]);
    this.#addButton.type = "button";
    this.#addButton.id = `${this.#idPrefix}-add`;
    this.#addButton.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;
    this.#addButton.addEventListener("click", () => this.#toggleAddForm());

    this.render();
  }

  /**
   * Replace backend data and clear local staging state.
   *
   * @param {Array<Object>} data
   *   New backend items.
   * @returns {void}
   */
  setData(data) {
    this.#cleanupPreviewUrls();

    this.#baseItems = Array.isArray(data) ? [...data] : [];
    this.#stagedAdds = [];
    this.#stagedDeletes.clear();
    this.#addForm = null;

    this.render();
  }

  /**
   * Return staged new items.
   *
   * @returns {Array<Object>}
   *   Items pending upload.
   */
    #getItemsToAdd() {
    return [...this.#stagedAdds];
  }

  /**
   * Return ids of backend items staged for deletion.
   *
   * @returns {Array<string>}
   *   Item ids staged for delete.
   */
    #getItemsToDelete() {
    return [...this.#stagedDeletes];
  }

  /**
   * Return the full editor state.
   *
   * @returns {{
   *   toAdd: Array<Object>,
   *   toDelete: Array<string>
   * }}
   *   Full state snapshot.
   */
  getPendingChanges() {
    console.log(this.#getItemsToAdd())
    return {
      toAdd: this.#getItemsToAdd(),
      toDelete: this.#getItemsToDelete(),
    };
  }

  /**
   * Render the full editor UI.
   *
   * @returns {void}
   */
  render() {
    this.#container.innerHTML = "";

    const items = this.#getVisibleItems();

    if (!items.length) {
      const empty = Utils.createElement("div", ["text-muted"]);
      empty.textContent = "No finder charts available.";
      this.#container.appendChild(empty);
    } else {
      const table = this.#buildTable();
      this.#tableBox.innerHTML = "";
      this.#tableBox.appendChild(table);

      for (const item of items) {
        this.#tbody.appendChild(this.#row(item));
      }

      this.#container.appendChild(this.#tableBox);
    }

    this.#container.appendChild(Utils.createElement("hr", ["my-1"]));

    if (this.#addForm) {
      this.#container.appendChild(this.#addForm);
    } else {
      const controls = Utils.createElement("div", [
        "d-flex",
        "gap-2",
        "flex-wrap",
      ]);
      controls.appendChild(this.#addButton);
      this.#container.appendChild(controls);
    }
  }

  /**
   * Build the finder chart table shell.
   *
   * @returns {HTMLTableElement}
   *   Table element with initialized tbody.
   */
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

  /**
   * Build the visible list used for rendering.
   *
   * @returns {Array<Object>}
   *   Combined list of saved and staged items.
   */
  #getVisibleItems() {
    const base = this.#baseItems.map((item) => ({
      ...item,
      rowState: this.#stagedDeletes.has(String(item.id))
        ? "staged-delete"
        : "saved",
    }));

    const adds = this.#stagedAdds.map((item) => ({
      ...item,
      id: item.tempId,
      rowState: "staged-add",
    }));

    return [...base, ...adds];
  }

  /**
   * Build a single table row for a finder chart item.
   *
   * @param {Object} item
   *   Renderable finder chart item.
   * @returns {HTMLTableRowElement}
   *   Table row element.
   */
  #row(item) {
     const tr = document.createElement("tr");
   
     let updatedContent;
   
     if (item.rowState === "staged-add") {
       tr.classList.add("table-secondary");
       updatedContent = this.#createBadge(" Upload pending", "success" , "fa-clock");
     } else if (item.rowState === "staged-delete") {
       tr.classList.add("table-secondary");
       updatedContent = this.#createBadge(" Marked for removal", "danger", "fa-trash");
     } else {
       updatedContent = this.#formatDate(item.updatedAt);
     }
   
     tr.appendChild(this.#cellFilename(item.fileName ?? "-", item.rowState));
     tr.appendChild(this.#cellContent(item.description ?? "-"));
     tr.appendChild(this.#cellContent(updatedContent));
     tr.appendChild(this.#cellActions(item));
   
     return tr;
   }
  /**
   * Build the filename cell with an icon representing the row state.
   *
   * @param {string} name
   *   File name to display.
   * @param {string} [state="saved"]
   *   Row state.
   * @returns {HTMLTableCellElement}
   *   Filename cell.
   */
  #cellFilename(name, state = "saved") {
    const td = document.createElement("td");

    const wrap = Utils.createElement("div", [
      "d-flex",
      "gap-2",
      "align-items-center",
    ]);

    let iconClass = "fa-file";
    let colorClass = "text-muted";

    if (state === "staged-add") {
      iconClass = "fa-file-circle-plus";
    }

    if (state === "staged-delete") {
      iconClass = "fa-file-circle-minus";
    }

    wrap.appendChild(
      Utils.createElement("i", [
        "fa-solid",
        iconClass,
        colorClass,
      ]),
    );

    const span = document.createElement("span");
    span.textContent = name ?? "-";
    wrap.appendChild(span);
    td.appendChild(wrap);
    return td;
  }

  /**
   * Build a table cell that can contain text or a badge.
   *
   * @param {string|HTMLElement} content
   * @returns {HTMLTableCellElement}
   */
  #cellContent(content) {
    const td = document.createElement("td");
    td.classList.add("text-center");
    if (content instanceof HTMLElement) {
      td.appendChild(content);
    } else {
      td.textContent = content ?? "-";
    }
  
    return td;
  }
  /**
   * Create a reusable action button.
   *
   * @param {Object} options
   *   Button options.
   * @param {string[]} options.classes
   *   CSS classes for the button element.
   * @param {string} options.icon
   *   Font Awesome icon class without the `fa-solid` prefix.
   * @param {string} options.title
   *   Button title attribute.
   * @param {boolean} [options.disabled=false]
   *   Whether the button should be disabled.
   * @param {Function} [options.onClick]
   *   Click handler.
   * @returns {HTMLButtonElement}
   *   Configured button element.
   */
  #createActionButton({
    classes = [],
    icon,
    title,
    disabled = false,
    onClick = null,
  }) {
    const button = Utils.createElement("button", classes);
    button.type = "button";
    button.innerHTML = `<i class="fa-solid ${icon}"></i>`;
    button.title = title;
    button.disabled = disabled;

    if (typeof onClick === "function") {
      button.addEventListener("click", onClick);
    }

    return button;
  }
  /**
   * Append multiple buttons into an action wrapper.
   *
   * @param {HTMLElement} wrap
   *   Container where buttons will be appended.
   * @param {Array<HTMLButtonElement|null|undefined|false>} buttons
   *   Buttons to append.
   * @returns {void}
   */
  #appendButtons(wrap, buttons) {
    buttons.filter(Boolean).forEach((btn) => wrap.appendChild(btn));
  }

  /**
   * Build the actions cell for an item.
   *
   * @param {Object} item
   *   Renderable finder chart item.
   * @returns {HTMLTableCellElement}
   *   Actions cell.
   */
  #cellActions(item) {
    const td = document.createElement("td");
    td.className = "text-end";

    const wrap = Utils.createElement("div", ["d-inline-flex", "gap-2"]);

    if (item.rowState === "staged-add") {
      const previewBtn = this.#createActionButton({
        classes: ["btn", "btn-sm", "btn-secondary"],
        icon: "fa-eye",
        title: "Preview",
        onClick: () => {
          if (item.previewUrl) {
            this.#showPreview(item.previewUrl);
          }
        },
      });

      const downloadBtn = this.#createActionButton({
        classes: ["btn", "btn-sm", "btn-outline-secondary"],
        icon: "fa-download",
        title: "No allowed",
        disabled: true,
      });

      const removeBtn = this.#createActionButton({
        classes: ["btn", "btn-sm", "btn-outline-danger"],
        icon: "fa-trash",
        title: "Delete",
        onClick: () => {
          this.#dispatch({
            type: "REMOVE_STAGED_ADD",
            payload: { tempId: item.tempId },
          });
        },
      });

      this.#appendButtons(wrap, [previewBtn, downloadBtn, removeBtn]);
      td.appendChild(wrap);
      return td;
    }

    const previewBtn = this.#createActionButton({
      classes: ["btn", "btn-sm", "btn-secondary"],
      icon: "fa-eye",
      title: "Preview",
      onClick: async () => {
        try {
          const res = await this.#callbacks.onFinderChartDownload?.({
            attachmentId: String(item.id),
          });
          const url = res?.url;
          if (!url) throw new Error("Missing url for preview.");
          this.#showPreview(url);
        } catch (err) {
          console.error("FinderChartEditor preview error:", err);
        }
      },
    });

    const downloadBtn = this.#createActionButton({
      classes: ["btn", "btn-sm", "btn-outline-primary"],
      icon: "fa-download",
      title: "Download",
      onClick: async () => {
        try {
          const res = await this.#callbacks.onFinderChartDownload?.({
            attachmentId: String(item.id),
          });
          const url = res?.url;
          if (!url) throw new Error("Missing url from download callback.");

          const a = document.createElement("a");
          a.href = url;
          a.download = item.fileName ?? "";
          document.body.appendChild(a);
          a.click();
          a.remove();
        } catch (err) {
          console.error("FinderChartEditor download error:", err);
        }
      },
    });

    if (item.rowState === "staged-delete") {
      const undoBtn = this.#createActionButton({
        classes: ["btn", "btn-sm", "btn-outline-warning"],
        icon: "fa-rotate-left",
        title: "Undo delete",
        onClick: () => {
          this.#dispatch({
            type: "UNSTAGE_DELETE",
            payload: { id: String(item.id) },
          });
        },
      });

      this.#appendButtons(wrap, [previewBtn, downloadBtn, undoBtn]);
      td.appendChild(wrap);
      return td;
    }

    const deleteBtn = this.#createActionButton({
      classes: ["btn", "btn-sm", "btn-outline-danger"],
      icon: "fa-trash",
      title: "Delete",
      onClick: () => {
        this.#dispatch({
          type: "STAGE_DELETE",
          payload: { id: String(item.id) },
        });
      },
    });

    this.#appendButtons(wrap, [previewBtn, downloadBtn, deleteBtn]);
    td.appendChild(wrap);

    return td;
  }

  /**
   * Toggle the add form visibility.
   *
   * @returns {void}
   */
  #toggleAddForm() {
    if (this.#addForm) {
      this.#addForm.remove();
      this.#addForm = null;
      this.render();
      return;
    }

    this.#addForm = this.#buildAddForm();
    this.render();
  }

  /**
   * Build the staged-add form.
   *
   * @returns {HTMLElement}
   *   Add form wrapper.
   */
  #buildAddForm() {
    const wrap = Utils.createElement("div", ["bg-body", "rounded-2"]);

    const form = Utils.createElement("form", [
      "d-flex",
      "flex-column",
      "gap-3",
    ]);

    const fileGroup = Utils.createElement("div", []);
    const fileId = `${this.#idPrefix}-file`;

    const fileLabel = Utils.createElement("label", ["form-label"]);
    fileLabel.htmlFor = fileId;
    fileLabel.textContent = "Select finder chart";

    const fileInput = Utils.createElement("input", ["form-control"]);
    fileInput.id = fileId;
    fileInput.type = "file";
    fileInput.name = "file";
    fileInput.accept = ".png,.jpg,.jpeg,image/png,image/jpeg";

    fileGroup.appendChild(fileLabel);
    fileGroup.appendChild(fileInput);

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

    const buttons = Utils.createElement("div", ["d-flex", "gap-2"]);

    const addBtn = Utils.createElement("button", ["btn", "btn-primary"]);
    addBtn.type = "button";
    addBtn.innerHTML = `<i class="fa-solid fa-plus"></i> Add`;

    const cancelBtn = Utils.createElement("button", ["btn", "btn-secondary"]);
    cancelBtn.type = "button";
    cancelBtn.textContent = "Cancel";

    cancelBtn.addEventListener("click", () => this.#toggleAddForm());

    addBtn.addEventListener("click", () => {
      const file = fileInput.files?.[0] ?? null;
      if (!file) {
        fileInput.focus();
        return;
      }

      this.#dispatch({
        type: "STAGE_ADD",
        payload: {
          file,
          description: descInput.value?.trim() || "",
        },
      });

      fileInput.value = "";
      descInput.value = "";
      this.#toggleAddForm();
    });

    form.appendChild(fileGroup);
    form.appendChild(descGroup);
    buttons.appendChild(addBtn);
    buttons.appendChild(cancelBtn);
    form.appendChild(buttons);

    wrap.appendChild(form);
    return wrap;
  }

  /**
   * Dispatch a state transition and re-render the editor.
   *
   * @param {{ type: string, payload?: any }} action
   *   State transition action.
   * @returns {void}
   */
  #dispatch(action) {
    const nextState = this.#reduce(
      {
        baseItems: this.#baseItems,
        stagedAdds: this.#stagedAdds,
        stagedDeletes: this.#stagedDeletes,
      },
      action,
    );

    this.#baseItems = nextState.baseItems;
    this.#stagedAdds = nextState.stagedAdds;
    this.#stagedDeletes = nextState.stagedDeletes;

    this.render();
  }

  /**
   * Apply a reducer action and return the next state.
   *
   * @param {{
   *   baseItems: Array<Object>,
   *   stagedAdds: Array<Object>,
   *   stagedDeletes: Set<string>
   * }} state
   *   Current editor state.
   * @param {{ type: string, payload?: any }} action
   *   Reducer action.
   * @returns {{
   *   baseItems: Array<Object>,
   *   stagedAdds: Array<Object>,
   *   stagedDeletes: Set<string>
   * }}
   *   Next editor state.
   */
  #reduce(state, action) {
    switch (action.type) {
      case "STAGE_ADD": {
        const { file, description } = action.payload ?? {};
        const tempId =
          `temp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

        return {
          ...state,
          stagedAdds: [
            ...state.stagedAdds,
            {
              tempId,
              file,
              fileName: file.name,
              description: description || "",
              previewUrl: URL.createObjectURL(file),
            },
          ],
        };
      }

      case "REMOVE_STAGED_ADD": {
        const tempId = String(action.payload?.tempId ?? "");
        const target = state.stagedAdds.find((x) => x.tempId === tempId);

        if (target?.previewUrl) {
          URL.revokeObjectURL(target.previewUrl);
        }

        return {
          ...state,
          stagedAdds: state.stagedAdds.filter((x) => x.tempId !== tempId),
        };
      }

      case "STAGE_DELETE": {
        const id = String(action.payload?.id ?? "");
        const nextDeletes = new Set(state.stagedDeletes);
        nextDeletes.add(id);

        return {
          ...state,
          stagedDeletes: nextDeletes,
        };
      }

      case "UNSTAGE_DELETE": {
        const id = String(action.payload?.id ?? "");
        const nextDeletes = new Set(state.stagedDeletes);
        nextDeletes.delete(id);

        return {
          ...state,
          stagedDeletes: nextDeletes,
        };
      }

      default:
        return state;
    }
  }
  /**
   * Create a Bootstrap badge element.
   *
   * @param {string} text
   * @param {string} variant
   * @returns {HTMLElement}
   */
  #createBadge(text, variant = "secondary", icon = null) {
    const span = document.createElement("span");
    span.className =`badge border text-${variant} border-${variant} bg-transparent`;
    if (icon) {
      span.innerHTML = `<i class="fa-solid ${icon}"></i>  ${text}`;
    } else {
      span.textContent = text;
    }
    return span;
  }

  /**
   * Format a date-like value for display.
   *
   * @param {string|Date|null|undefined} value
   *   Date-like value.
   * @returns {string}
   *   Formatted date string or fallback.
   */
  #formatDate(value) {
    if (!value) return "-";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString();
  }

  /**
   * Revoke all staged preview object URLs.
   *
   * @returns {void}
   */
  #cleanupPreviewUrls() {
    this.#stagedAdds.forEach((item) => {
      if (item.previewUrl) {
        URL.revokeObjectURL(item.previewUrl);
      }
    });
  }

  /**
   * Show the finder chart preview modal.
   *
   * @param {string} url
   *   Image URL to preview.
   * @returns {void}
   */
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
              <button
                type="button"
                class="btn-close"
                data-bs-dismiss="modal"
              ></button>
            </div>
            <div class="modal-body text-center">
              <img
                id="fc-preview-img"
                style="max-width:100%; max-height:70vh;"
              >
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
