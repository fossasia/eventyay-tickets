function docReady(fn) {
    // see if DOM is already available
    if (document.readyState === "complete" || document.readyState === "interactive") {
        // call on next available tick
        setTimeout(fn, 1);
    } else {
        document.addEventListener("DOMContentLoaded", fn);
    }
}

const initTabs = () => {
  let selectedTab = document.querySelector("input[name=tabs]:checked")
  if (!selectedTab) {
    selectedTab = document.querySelector("input[name=tabs]")
    if (!selectedTab) return
  }
  const fragment = window.location.hash.substr(1);
  if (fragment) {
    selectedTab = document.querySelector("input[name=tabs][id='" + fragment + "']") || selectedTab
  }
  selectedTab.checked = true
  document.querySelector("label.pretalx-tab-label[for='" + selectedTab.id + "']").parentElement.classList.add("active")

  document.querySelectorAll("label.pretalx-tab-label").forEach((element) => {
    element.addEventListener('click', (event) => {
      document.querySelectorAll(".pretalx-tab").forEach((element) => {
        element.classList.remove("active")
      })
      event.target.parentElement.classList.add("active")
      window.location.hash = event.target.attributes.for.nodeValue
    })
  })
}
docReady(initTabs)
