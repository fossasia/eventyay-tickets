window.addEventListener("load", function(event) {
  if ('scrollSnapAlign' in document.documentElement.style ||
      'webkitScrollSnapAlign' in document.documentElement.style ||
      'msScrollSnapAlign' in document.documentElement.style) {
    return
  }
  document.querySelector(".pretalx-schedule-day").forEach((element) => {
    element.style.scrollSnapType = null
  })
  document.querySelector(".pretalx-schedule-room").forEach((element) => {
    element.style.scrollSnapAlign = null
  })
})
