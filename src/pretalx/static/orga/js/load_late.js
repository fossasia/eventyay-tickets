document.addEventListener("DOMContentLoaded", function() {
  const element = document.querySelector("[data-toggle=sidebar]")
  if (element) {
    element.addEventListener("click", () => {
      document
        .querySelector(".flex-column.sidebar")
        .classList.toggle("sidebar-uncollapsed")
    })
  }
})
