const initColorPicker = (field) => {
    // We're creating a parent element to hold the colorpicker/preview and the input field
    const parentEl = document.createElement("div")
    parentEl.classList.add("colorpicker-wrapper", "input-group")
    const pickerEl = document.createElement("div")
    pickerEl.classList.add("input-group-prepend")
    const wrapperEl = document.createElement("div")
    wrapperEl.classList.add("input-group-text")
    const previewEl = document.createElement("div")
    previewEl.classList.add("colorpicker-preview")
    previewEl.style.backgroundColor = field.value

    wrapperEl.appendChild(previewEl)
    pickerEl.appendChild(wrapperEl)
    parentEl.appendChild(pickerEl)
    const fieldParent = field.parentNode
    fieldParent.replaceChild(parentEl, field)
    parentEl.appendChild(field)

    const picker = new Picker({
        parent: pickerEl,
        color: field.value,
        popup: "left",
        alpha: false,
        editor: false,
        onChange: (color) => updateContrast(field, color),
    })

    field.addEventListener("focus", () => {
        picker.openHandler()
    })
    previewEl.addEventListener("click", () => {
        picker.openHandler()
    })

    field.addEventListener("input", () => {
        picker.setColor(field.value)
    })
}

const updateContrast = (field, color) => {
    field.parentNode.parentNode.querySelector(
        ".colorpicker-preview",
    ).style.backgroundColor = color.hex
    // We're getting RRGGBBAA, but we don't want the alpha channel
    const c = contrast([255, 255, 255], color.rgba.slice(0, 3))
    if (!field.parentNode.parentNode.querySelector(".contrast-state")) {
        const note = document.createElement("div")
        note.classList.add("help-block", "contrast-state")
        field.parentNode.parentNode.appendChild(note)
    }
    const note = field.parentNode.parentNode.querySelector(".contrast-state")
    const goal = field.parentNode.parentNode.querySelector(".color-visible")
        ? "visible"
        : "readable"
    note.classList.remove("text-success")
    note.classList.remove("text-warning")
    note.classList.remove("text-danger")
    if (c > 7) {
        note.innerHTML =
            "<span class='fa fa-fw fa-check-circle'></span> Your color has great contrast and is very easy to read!"
        note.classList.add("text-success")
    } else if (c > 2.5) {
        note.innerHTML =
            "<span class='fa fa-fw fa-info-circle'></span> Your color has decent contrast and is probably easy enough to read!"
        note.classList.add("text-warning")
    } else {
        note.innerHTML =
            "<span class='fa fa-fw fa-warning'></span> Your color has bad contrast and will be hard to read."
        note.classList.add("text-danger")
    }
    if (goal === "visible") {
        // replace "read" with "see" in the info text
        note.innerHTML = note.innerHTML.replace("read", "see")
    }
}

const luminanace = (r, g, b) => {
    const a = [r, g, b].map((v) => {
        v /= 255
        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
    })
    return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722
}

const contrast = (rgb1, rgb2) => {
    const l1 = luminanace(rgb1[0], rgb1[1], rgb1[2]) + 0.05
    const l2 = luminanace(rgb2[0], rgb2[1], rgb2[2]) + 0.05
    const ratio = l1 / l2
    if (l2 > l1) {
        ratio = 1 / ratio
    }
    return ratio.toFixed(1)
}

onReady(() => {
    document.querySelectorAll("input.colorpicker").forEach((field) => {
        initColorPicker(field)
    })
})
