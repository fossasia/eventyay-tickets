let activeElement = null
let menu = null

const getSelection = () => {
    if (!activeElement) return ""
    let start = activeElement.selectionStart
    let finish = activeElement.selectionEnd
    if (start === undefined || finish === undefined) {
        return ""
    }
    return activeElement.value.substring(start, finish)
}

const getCursorPosition = (element) => {
    const div = document.createElement("div")
    const style = getComputedStyle(element)
    for (const prop of style) {
        div.style[prop] = style[prop]
    }
    div.style.height = "auto"
    div.style.position = "absolute"
    div.style.width = element.offsetWidth + "px"
    const text = element.value.substring(0, element.selectionStart)
    div.textContent = text
    const span = document.createElement("span")
    span.textContent = element.value.substring(element.selectionStart)
    div.appendChild(span)
    document.body.appendChild(div)
    const result = { x: span.offsetLeft, y: span.offsetTop }
    document.body.removeChild(div)
    return result
}

const updateMenu = () => {
    if (!menu) {
        return
    }
    if (!activeElement) {
        menu.classList.add("d-none")
        return
    }
    let sel = getSelection()
    if (!sel) {
        menu.classList.add("d-none")
        return
    }
    menu.classList.remove("d-none")

    const cursorPosition = getCursorPosition(activeElement)
    // get top of relative element to subtract from the cursor position
    const formOffsetTop = activeElement.getBoundingClientRect().top

    const menuOffsetHeight = 10
    const menuOffsetWidth = 0.2 * menu.querySelector("button").offsetWidth

    menu.style.left = activeElement.offsetLeft + cursorPosition.x - menuOffsetWidth + "px"
    menu.style.top = activeElement.offsetTop + cursorPosition.y - menuOffsetHeight + "px"
}

const censor = (ev) => {
    let sel = getSelection()
    if (!sel) {
        return
    }
    let start = activeElement.selectionStart
    let value = activeElement.value
    activeElement.value =
        value.substring(0, start) +
        "█".repeat(sel.length) +
        value.substring(start + sel.length, value.length)
    activeElement = null
    updateMenu()
}

const onSelect = (ev) => {
    activeElement = ev.target
    updateMenu()
}
const triggerCensoring = () => {
    menu = document.querySelector("#anon-menu")
    menu.querySelector("button").addEventListener("click", censor)
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
