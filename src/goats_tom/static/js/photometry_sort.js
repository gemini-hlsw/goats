/**
 * Sorts the photometry table in place.
 *
 * The table renders every data point, so the browser already holds the rows the
 * server would re-send: reloading the whole target page to reorder them also
 * throws away the scroll position, the filter text and the share selection.
 *
 * The `<th>` links rendered by `{% sortable_header %}` keep working when this
 * script does not run, so ordering still degrades to a server round trip. The
 * chosen order is mirrored into the URL, so a manual reload shows the same
 * thing and the link stays shareable.
 */
class PhotometryTableSort {
  /** Query parameter `{% sortable_header %}` writes for this table. */
  static PARAM = "order_photometry";

  constructor(table) {
    this.table = table;
    this.tbody = table.tBodies[0];
    this.links = Array.from(
      table.querySelectorAll(`thead a[href*="${PhotometryTableSort.PARAM}="]`)
    );
    for (const link of this.links) {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        this.sortBy(PhotometryTableSort.orderOf(link));
      });
    }
  }

  /** The ordering a header link would apply, e.g. `"-mjd"`. */
  static orderOf(link) {
    const url = new URL(link.getAttribute("href"), window.location.href);
    return url.searchParams.get(PhotometryTableSort.PARAM);
  }

  /**
   * Value a row sorts on, or `NaN` when it has none.
   *
   * Mirrors `_photometry_sort_key` in `templatetags/tom_overrides.py`: MJD may
   * arrive as a string or be missing entirely.
   */
  static valueOf(row, field) {
    if (field === "mjd") {
      const mjd = row.dataset.sortMjd;
      return mjd === "" || mjd === undefined ? NaN : Number(mjd);
    }
    return Utils.utcDateValue(row.dataset.sortTimestamp);
  }

  /** Reorder the rows and bring the headers and the URL along. */
  sortBy(order) {
    if (!order) return;
    const field = order.replace(/^-/, "");
    const descending = order.startsWith("-");
    const factor = descending ? -1 : 1;

    const rows = Array.from(this.tbody.querySelectorAll("tr[data-sort-pk]"));
    rows.sort((a, b) => {
      const left = PhotometryTableSort.valueOf(a, field);
      const right = PhotometryTableSort.valueOf(b, field);
      // Rows without a value stay last whichever way the column is sorted.
      if (Number.isNaN(left) !== Number.isNaN(right)) return Number.isNaN(left) ? 1 : -1;
      if (Number.isNaN(left)) return 0;
      const bypk = Number(a.dataset.sortPk) - Number(b.dataset.sortPk);
      return (left - right) * factor || bypk * factor;
    });
    for (const row of rows) this.tbody.appendChild(row);

    // The placeholder is a sibling of the data rows, so it has to be pushed back
    // down after they are re-appended.
    const placeholder = this.tbody.querySelector("#photDataNoMatchesRow");
    if (placeholder) this.tbody.appendChild(placeholder);

    this.refreshHeaders(order);
    PhotometryTableSort.rememberInUrl(order);
  }

  /** Point each header at its next ordering and show the current one. */
  refreshHeaders(order) {
    const field = order.replace(/^-/, "");
    const descending = order.startsWith("-");
    for (const link of this.links) {
      const linkField = PhotometryTableSort.orderOf(link).replace(/^-/, "");
      const active = linkField === field;
      // Clicking the sorted column flips it; the others start newest first.
      const next = active && descending ? linkField : `-${linkField}`;
      const url = new URL(link.getAttribute("href"), window.location.href);
      url.searchParams.set(PhotometryTableSort.PARAM, next);
      link.setAttribute("href", `${url.search}`);
      PhotometryTableSort.setIcon(link, active ? (descending ? "desc" : "asc") : null);
    }
  }

  /** Show the sort direction, or the neutral icon when the column is not sorted. */
  static setIcon(link, direction) {
    const icon = link.querySelector("i");
    if (!icon) return;
    if (!direction) {
      icon.classList.remove("fa-arrow-up-short-wide", "fa-arrow-down-wide-short");
      icon.classList.add("fa-sort", "text-muted");
      return;
    }
    Utils.updateDateSortIcon(icon, direction);
  }

  /** Keep the address bar in step, the way the tab selection already does. */
  static rememberInUrl(order) {
    const url = new URL(window.location.href);
    url.searchParams.set(PhotometryTableSort.PARAM, order);
    window.history.replaceState({}, document.title, url.toString());
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const table = document.getElementById("photData");
  if (table && table.tBodies.length) new PhotometryTableSort(table);
});
