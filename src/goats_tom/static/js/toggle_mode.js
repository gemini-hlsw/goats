(() => {
  "use strict";

  /**
   * Retrieves the currently stored theme from localStorage.
   * @returns {string|null} The stored theme or `null` if not set.
   */
  const getStoredTheme = () => localStorage.getItem("theme");

  /**
   * Stores the specified theme in localStorage.
   * @param {string} theme - The theme to store ('light' or 'dark').
   */
  const setStoredTheme = (theme) => localStorage.setItem("theme", theme);

  /**
   * Determines the preferred theme based on the user's system preference or the stored theme.
   * @returns {string} 'dark' if the user prefers a dark theme, 'light' otherwise.
   */
  const getPreferredTheme = () => {
    const storedTheme = getStoredTheme();
    // Return the stored theme if it exists.
    if (storedTheme) {
      return storedTheme;
    }
    // Check the system preference for dark mode.
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };

  /**
   * Sets the theme by updating the document's attribute and storing the selection.
   * @param {string} theme - The theme to set ('light' or 'dark').
   */
  const setTheme = (theme) => {
    document.documentElement.setAttribute("data-bs-theme", theme);
    setStoredTheme(theme);
  };

  // Initialize theme on script load.
  setTheme(getPreferredTheme());

  /**
   * Updates the theme toggle button icon based on the current theme.
   * @param {string} theme - The current theme ('light' or 'dark').
   */
  const updateThemeIcon = (theme) => {
    const toggleButton = document.getElementById("colorThemeToggle");
    // Set the toggle button's innerHTML based on the current theme.
    if (theme === "dark") {
      toggleButton.innerHTML = '<i class="fa-solid fa-sun"></i><span class="d-md-none ms-2">Theme</span>';
    } else {
      toggleButton.innerHTML = '<i class="fa-solid fa-moon"></i><span class="d-md-none ms-2">Theme</span>';
    }
  };

  // Listen for system theme change and update theme accordingly if not explicitly set by the user.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    const storedTheme = getStoredTheme();
    // Update the theme only if it's not explicitly set to 'light' or 'dark'.
    if (storedTheme !== "light" && storedTheme !== "dark") {
      setTheme(getPreferredTheme());
    }
  });

  // Setup theme toggle button and update icon on DOMContentLoaded.
  window.addEventListener("DOMContentLoaded", () => {
    // Update the theme icon on page load.
    updateThemeIcon(getStoredTheme());

    // Add click event listener to the theme toggle button.
    document.getElementById("colorThemeToggle").addEventListener("click", (e) => {
      e.preventDefault();
      const currentTheme = getStoredTheme();
      const newTheme = currentTheme === "dark" ? "light" : "dark";
      // Update the theme and the icon on toggle.
      setTheme(newTheme);
      updateThemeIcon(newTheme);
    });
  });

})();