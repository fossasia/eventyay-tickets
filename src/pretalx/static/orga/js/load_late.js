document.addEventListener("DOMContentLoaded", function() {
  const element = document.querySelector("[data-toggle=sidebar]")
  const sidebar = document.querySelector("aside.sidebar")
  const cls = "sidebar-uncollapsed"
  if (sidebar && localStorage["sidebarVisible"]) {
    sidebar.classList.add(cls)
  }
  if (sidebar && element) {
    element.addEventListener("click", () => {
      sidebar.classList.toggle(cls)
      localStorage["sidebarVisible"] = sidebar.classList.contains(cls) ? "1" : ""
    })
  }
})
