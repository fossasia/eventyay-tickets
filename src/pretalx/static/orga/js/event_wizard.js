const number = new Date().getYear() - 100
const updateSlug = ev => {
  const value = document.querySelector("#event-name input").value
  const matches = value.match(/\b(\w)/g)
  if (matches)
    document.querySelector("#id_basics-slug").value = matches.join("") + number
}
document.querySelectorAll("#event-name input").forEach(element => {
  element.addEventListener("input", updateSlug)
})
document.querySelector("#id_basics-slug").addEventListener("input", ev => {
  document.querySelectorAll("#event-name input").forEach(element => {
    element.removeEventListener("input", updateSlug)
  })
})
