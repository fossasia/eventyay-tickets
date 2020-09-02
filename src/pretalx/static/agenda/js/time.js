document.addEventListener("DOMContentLoaded", function() {
  function updateCurrentTalk() {
    const now = moment()
    document.querySelectorAll(".pretalx-schedule-talk").forEach(element => {
      const start = moment(element.dataset.start)
      const end = moment(element.dataset.end)
      if (start < now && end > now) {
        element.classList.add("active")
      } else {
        element.classList.remove("active")
      }
    })
  }

  updateCurrentTalk()
  setInterval(updateCurrentTalk, 60 * 60)
})
