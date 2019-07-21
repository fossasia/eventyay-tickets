if ("serviceWorker" in navigator) {
  const source = document.querySelector("#offline-vars")
  if (source) {
    navigator.serviceWorker.register("/sw.js", {
      scope: source.getAttribute("data-event"),
    })
  }
}
