/* Handle Markdown */
let dirtyInputs = []
const options = {
  breaks: true,
  gfm: true,
  pedantic: false,  // Drawback: will render lists without blank lines correctly
  silent: false,
  smartLists: true,
  tables: true,
}

function checkForChanges() {
  if (dirtyInputs.length) {
    dirtyInputs.forEach(element => {
      const inputElement = element.querySelector("textarea")
      const outputElement = element.querySelector(".preview")
      outputElement.innerHTML = marked.parse(inputElement.value, options)
    })
    dirtyInputs = []
  }
  checkChangeTimeout = window.setTimeout(checkForChanges, 100)
}

const warnFileSize = (element) => {
  const warning = document.createElement("div")
  warning.classList = ["invalid-feedback"]
  warning.textContent = element.dataset.sizewarning
  element.parentElement.appendChild(warning)
  element.classList.add("is-invalid")
}
const unwarnFileSize = (element) => {
  element.classList.remove("is-invalid")
  const warning = element.parentElement.querySelector(".invalid-feedback")
  if (warning) element.parentElement.removeChild(warning)
}

/* Register handlers */
window.onload = () => {
  document.querySelectorAll(".markdown-wrapper").forEach(element => {
    const inputElement = element.querySelector("textarea")
    const outputElement = element.querySelector(".preview")
    outputElement.innerHTML = marked.parse(inputElement.value, options)
    const handleInput = () => {
      dirtyInputs.push(element)
    }
    inputElement.addEventListener("change", handleInput, false)
    inputElement.addEventListener("keyup", handleInput, false)
    inputElement.addEventListener("keypress", handleInput, false)
    inputElement.addEventListener("keydown", handleInput, false)
  })
  checkForChanges()

  document.querySelectorAll("input[data-maxsize][type=file]").forEach(element => {
    const checkFileSize = () => {
      const files = element.files
      if (!files || !files.length) {
        unwarnFileSize(element)
      } else {
        maxsize = parseInt(element.dataset.maxsize)
        if (files[0].size > maxsize) { warnFileSize(element) } else { unwarnFileSize(element) }
      }
    }
    element.addEventListener("change", checkFileSize, false)
  })
}

// Make sure the main form doesn't have unsaved changes before leaving
document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('form[method="post"]')
    if (!form) return

    const originalData = {}
    // Populate original data after a short delay to make sure the form is fully loaded
    // and that any script interactions have run
    setTimeout(() => {
        new FormData(form).forEach((value, key) => originalData[key] = value)
    }, 1000)

    const isDirty = () => {
        if (Object.keys(originalData).length === 0) return false
        const currentData = {}
        new FormData(form).forEach((value, key) => currentData[key] = value)
        return JSON.stringify(originalData) !== JSON.stringify(currentData)
    }
    const handleUnload = (e) => {
        if (isDirty()) {
            e.preventDefault()
        }
    };

    form.addEventListener('submit', () => {
        window.removeEventListener('beforeunload', handleUnload)
    });
    window.addEventListener('beforeunload', handleUnload)
});
