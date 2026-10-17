/**
 * Points the arrow of a navbar menu at the icon of the item that opened it.
 *
 * The arrow is drawn by CSS on the toggle; this sets where along it, from the
 * icon's position measured when the menu opens.
 */
document.addEventListener("show.bs.dropdown", (event) => {
  const toggle = event.target;
  if (!toggle.closest(".navbar-tools")) return;
  // Font Awesome swaps each <i> for an <svg> once it loads.
  const icon = toggle.querySelector("svg, i");
  if (!icon) return;

  const iconBox = icon.getBoundingClientRect();
  const toggleBox = toggle.getBoundingClientRect();
  const center = iconBox.left + iconBox.width / 2 - toggleBox.left;
  toggle.style.setProperty("--menu-arrow-x", `${center}px`);
});
