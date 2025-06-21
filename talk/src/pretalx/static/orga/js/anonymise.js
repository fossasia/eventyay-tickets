let ACTIVE_ELEMENT = null
let MENU = null

const getSelection = () => {
    if (!ACTIVE_ELEMENT) return ""
    let start = ACTIVE_ELEMENT.selectionStart
    let finish = ACTIVE_ELEMENT.selectionEnd
    if (start === undefined || finish === undefined) {
        return ""
    }
    return ACTIVE_ELEMENT.value.substring(start, finish)
}

const updateMenu = () => {
    if (!MENU) {
        return
    }
    if (!ACTIVE_ELEMENT) {
        MENU.classList.add("d-none")
        return
    }
    let sel = getSelection()
    if (!sel) {
        MENU.classList.add("d-none")
        return
    }
    MENU.classList.remove("d-none")
    MENU.style.top = ACTIVE_ELEMENT.offsetTop + "px"
}

const censor = (ev) => {
    let sel = getSelection()
    if (!sel) {
        return
    }
    let start = ACTIVE_ELEMENT.selectionStart
    let value = ACTIVE_ELEMENT.value
    ACTIVE_ELEMENT.value =
        value.substring(0, start) +
        "█".repeat(sel.length) +
        value.substring(start + sel.length, value.length)
    ACTIVE_ELEMENT = null
    updateMenu()
}

const onSelect = (ev) => {
    ACTIVE_ELEMENT = ev.target
    updateMenu()
}
const triggerCensoring = () => {
    MENU = document.querySelector("#anon-menu")
    MENU.querySelector("button").addEventListener("click", censor)
    document
        .querySelectorAll(".anonymised input, .anonymised textarea")
        .forEach((element) => {
            element.addEventListener("keyup", onSelect)
            element.addEventListener("mouseup", onSelect)
            element.addEventListener("compositionupdate", onSelect)
            element.addEventListener("blur", onSelect)
        })
}
onReady(triggerCensoring)
