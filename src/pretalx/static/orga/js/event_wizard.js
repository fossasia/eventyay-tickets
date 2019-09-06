const number = new Date().getYear() + 1900
const updateSlug = ev => {
  const value = document.querySelector("#event-name input").value
  let slug = value.replace(/\W+/g, '-').toLowerCase()
  if (slug && (slug.indexOf(number) == -1))
    slug += "-" + number
  if (slug)
    document.querySelector("#id_basics-slug").value = slug
}
document.querySelectorAll("#event-name input").forEach(element => {
  element.addEventListener("input", updateSlug)
})
document.querySelector("#id_basics-slug").addEventListener("input", ev => {
  document.querySelectorAll("#event-name input").forEach(element => {
    element.removeEventListener("input", updateSlug)
  })
})
