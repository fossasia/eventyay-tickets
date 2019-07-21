let dirtyInputs = []
const options = {
  baseUrl: null,
  breaks: false,
  gfm: true,
  headerIds: true,
  headerPrefix: "",
  highlight: null,
  langPrefix: "language-",
  mangle: true,
  pedantic: false,
  sanitize: false,
  sanitizer: null,
  silent: false,
  smartLists: true,
  smartypants: false,
  tables: true,
  xhtml: false,
}

function checkForChanges() {
  if (dirtyInputs.length) {
    dirtyInputs.forEach(element => {
      const inputElement = element.querySelector("textarea")
      const outputElement = element.querySelector(".preview")
      outputElement.innerHTML = marked(inputElement.value)
    })
    dirtyInputs = []
  }
  checkChangeTimeout = window.setTimeout(checkForChanges, 100)
}
window.onload = () => {
  document.querySelectorAll(".markdown-wrapper").forEach(element => {
    const inputElement = element.querySelector("textarea")
    const outputElement = element.querySelector(".preview")
    outputElement.innerHTML = marked(inputElement.value)
    const handleInput = () => {
      dirtyInputs.push(element)
    }
    inputElement.addEventListener("change", handleInput, false)
    inputElement.addEventListener("keyup", handleInput, false)
    inputElement.addEventListener("keypress", handleInput, false)
    inputElement.addEventListener("keydown", handleInput, false)
  })
  checkForChanges()
}
