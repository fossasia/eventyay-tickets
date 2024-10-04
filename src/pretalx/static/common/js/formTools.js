/* This script will be included on all pages with forms.
 * (And on all pages on the backend in general). */

/* Handle Markdown: run marked on change and activate tabs */
let dirtyInputs = []
const options = {
    breaks: true,
    gfm: true,
    pedantic: false, // Drawback: will render lists without blank lines correctly
    silent: false,
    smartLists: true,
    tables: true,
}

const checkForChanges = () => {
    if (dirtyInputs.length) {
        dirtyInputs.forEach((element) => {
            const inputElement = element.querySelector("textarea")
            const outputElement = element.querySelector(".preview")
            outputElement.innerHTML = DOMPurify.sanitize(
                marked.parse(inputElement.value, options),
            )
        })
        dirtyInputs = []
    }
    window.setTimeout(checkForChanges, 100)
}

const initMarkdown = (element) => {
    const inputElement = element.querySelector("textarea")
    const outputElement = element.querySelector(".markdown-preview")
    outputElement.innerHTML = DOMPurify.sanitize(
        marked.parse(inputElement.value, options),
    )
    const handleInput = () => {
        dirtyInputs.push(element)
    }
    inputElement.addEventListener("change", handleInput, false)
    inputElement.addEventListener("keyup", handleInput, false)
    inputElement.addEventListener("keypress", handleInput, false)
    inputElement.addEventListener("keydown", handleInput, false)

    // Activate tabs
    const updateTabPanels = (ev) => {
        const selectedTab = ev.target
            .closest("[role=tablist]")
            .querySelector("input[role=tab]:checked")
        if (!selectedTab) return
        const selectedPanel = document.getElementById(
            selectedTab.getAttribute("aria-controls"),
        )
        if (!selectedPanel) return
        selectedTab.parentElement
            .querySelectorAll(`[role=tab][aria-selected=true]`)
            .forEach((element) => {
                element.setAttribute("aria-selected", "false")
            })
        selectedPanel.parentElement
            .querySelectorAll("[role=tabpanel][aria-hidden=false]")
            .forEach((element) => {
                element.setAttribute("aria-hidden", "true")
            })
        selectedTab.setAttribute("aria-selected", "true")
        selectedPanel.setAttribute("aria-hidden", "false")
    }
    element.parentElement.querySelectorAll("input[role=tab]").forEach((tab) => {
        tab.addEventListener("change", updateTabPanels)
    })
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

const initFileSizeCheck = (element) => {
    const checkFileSize = () => {
        const files = element.files
        if (!files || !files.length) {
            unwarnFileSize(element)
        } else {
            maxsize = parseInt(element.dataset.maxsize)
            if (files[0].size > maxsize) {
                warnFileSize(element)
            } else {
                unwarnFileSize(element)
            }
        }
    }
    element.addEventListener("change", checkFileSize, false)
}

const isVisible = (element) => {
    if (!element) return false
    return !element.hidden && !element.classList.contains("d-none")
}

const initSelect = (element) => {
    const removeItemButton =
        !element.readonly && (!element.required || element.multiple)
    let showPlaceholder = !!element.title
    if (showPlaceholder) {
        // Make sure we don't show a placeholder that is obvious from context
        if (element.getAttribute("aria-describedby")) {
            const describedBy = document.getElementById(
                element.getAttribute("aria-describedby"),
            )
            if (isVisible(describedBy)) {
                showPlaceholder = describedBy.textContent !== element.title
            }
        }
    }
    if (showPlaceholder) {
        const label = document.querySelector(`label[for=${element.id}]`)
        if (isVisible(label)) {
            showPlaceholder = label.textContent !== element.title
        }
    }
    const choicesOptions = {
        removeItems: !element.readonly,
        removeItemButton:
            !element.readonly && (!element.required || element.multiple),
        removeItemButtonAlignLeft: true,
        searchFields: ["label"],
        searchEnabled: true,
        searchResultLimit: -1,
        resetScrollPosition: false,
        shouldSort: false,
        placeholderValue: showPlaceholder ? element.title : null,
        itemSelectText: "",
        addItemText: "",
        removeItemLabelText: "×",
        removeItemIconText: "×",
        maxItemText: "",
    }
    if (element.querySelectorAll("option[data-description]").length || element.querySelectorAll("option[data-color]").length) {
        choicesOptions.callbackOnCreateTemplates = (strToEl, escapeForTemplates, getClassNames) => ({
            choice: (allowHTML, classNames, choice, selectedText, groupName) => {
                let originalResult = Choices.defaults.templates.choice(allowHTML, classNames, choice, selectedText, groupName)
                if (classNames.element && classNames.element.dataset.description) {
                    console.log(originalResult)
                    console.log(classNames.element)
                    originalResult.innerHTML += `<div class="choice-item-description">${classNames.element.dataset.description}</div>`
                }
                if (classNames.element && classNames.element.dataset.color) {
                    originalResult.classList.add("choice-item-color")
                    originalResult.style.setProperty("--choice-color", classNames.element.dataset.color)
                }
                return originalResult
            }
        })
    }
    new Choices(element, choicesOptions)
}

// Make sure the main form doesn't have unsaved changes before leaving
const initFormChanges = (form) => {
    const originalData = {}
    // Populate original data after a short delay to make sure the form is fully loaded
    // and that any script interactions have run
    setTimeout(() => {
        new FormData(form).forEach((value, key) => (originalData[key] = value))
    }, 1000)

    const isDirty = (form) => {
        if (Object.keys(originalData).length === 0) return false
        const currentData = {}
        new FormData(form).forEach((value, key) => (currentData[key] = value))
        return JSON.stringify(originalData) !== JSON.stringify(currentData)
    }

    const handleUnload = (e) => {
        if (isDirty(form)) {
            e.preventDefault()
        }
    }

    form.addEventListener("submit", () => {
        window.removeEventListener("beforeunload", handleUnload)
    })
    window.addEventListener("beforeunload", handleUnload)
}

const addDateLimit = (element, other, limit) => {
    const otherElement = document.querySelector(other)
    if (otherElement) {
        console.log("Adding date limit", limit, otherElement)
        otherElement.addEventListener("change", () => {
            element.setAttribute(limit, otherElement.value)
        })
        element.setAttribute(limit, otherElement.value)
    }
}

// Handle date and datetime fields:
// - Make sure the picker opens on focus
// - Use the data-date-after and data-date-before attributes to set min/max dynamically on change
const initDateFields = () => {
    document
        .querySelectorAll("input[type=date], input[type=datetime-local]")
        .forEach((element) => {
            if (element.readOnly || element.disabled) return
            // Delay, because otherwise clicking the *icon* in FF will make the picker immediately disappear again
            element.addEventListener("focus", () =>
                setTimeout(() => element.showPicker(), 70),
            )
            if (element.dataset.dateBefore)
                addDateLimit(element, element.dataset.dateBefore, "max")
            if (element.dataset.dateAfter)
                addDateLimit(element, element.dataset.dateAfter, "min")
        })
}

/* Register handlers */
onReady(() => {
    document
        .querySelectorAll(".markdown-wrapper")
        .forEach((element) => initMarkdown(element))
    document
        .querySelectorAll("input[data-maxsize][type=file]")
        .forEach((element) => initFileSizeCheck(element))
    document
        .querySelectorAll(".select2")
        .forEach((element) => initSelect(element))
    document
        .querySelectorAll("form[method=post]")
        .forEach((form) => initFormChanges(form))
    checkForChanges()
    initDateFields()
})
