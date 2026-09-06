/* These functions are used in the email editor, in order to insert clicked
 * placeholders into the currently focused input field. */

let lastFocusedInput = null

const makePlaceholderActive = (placeholder) => {
    placeholder.querySelector(".unavailable").classList.add("d-none")
    placeholder.querySelector(".list-group").classList.remove("d-none")
}

const makePlaceholderInactive = (placeholder) => {
    placeholder.querySelector(".unavailable").classList.remove("d-none")
    placeholder.querySelector(".list-group").classList.add("d-none")
}

const updateVisiblePlaceholders = (speakerSelect) => {
    const groups = ["#placeholder-submission", "#placeholder-slot"]
        .map((selector) => document.querySelector(selector))
        .filter((group) => group)
    const update = speakerSelect.selectedOptions.length === 0
        ? makePlaceholderActive
        : makePlaceholderInactive
    groups.forEach(update)
}

const setDrawerOpen = (drawer, toggle, search, open) => {
    drawer.hidden = !open
    const form = drawer.closest("form")
    if (form) {
        form.classList.toggle("placeholder-drawer-open", open)
    }
    if (toggle) {
        toggle.setAttribute("aria-expanded", open ? "true" : "false")
    }
    if (open && search) {
        search.focus()
    }
}

const filterPlaceholders = (drawer, empty, query) => {
    const needle = query.trim().toLowerCase()
    let matches = 0
    drawer.querySelectorAll(".card").forEach((group) => {
        let groupMatches = 0
        group.querySelectorAll(".placeholder").forEach((item) => {
            const match = item.dataset.placeholder.toLowerCase().includes(needle)
            item.classList.toggle("d-none", !match)
            if (match) groupMatches++
        })
        group.classList.toggle("d-none", groupMatches === 0)
        matches += groupMatches
    })
    if (empty) {
        empty.classList.toggle("d-none", matches > 0)
    }
}

onReady(() => {
    lastFocusedInput = document.querySelector("#id_text_0") || document.querySelector("#id_message_0")

    // When an input matching id_text_\d or id_subject\d is focused, set lastFocusedInput to that input
    document
        .querySelectorAll('textarea[id^="id_text_"], textarea[id^="id_message_"], input[id^="id_subject"]')
        .forEach((input) => {
            input.addEventListener("focus", () => {
                lastFocusedInput = input
            })
        })

    // When any placeholder is clicked, insert its text into lastFocusedInput
    document.querySelectorAll(".placeholder").forEach((placeholder) => {
        placeholder.addEventListener("click", (e) => {
            if (e.target.classList.contains("fa-question")) {
                return
            }
            if (lastFocusedInput) {
                const placeholderValue = "{" + placeholder.dataset.placeholder + "}"
                const content = lastFocusedInput.value
                let start = lastFocusedInput.selectionStart
                let end = lastFocusedInput.selectionEnd
                const selectedPlaceholderStart = /\{\w*$/.exec(
                    content.substring(0, start),
                )
                var selectedPlaceholderEnd = /^\w*\}/.exec(
                    content.substring(end),
                )
                if (selectedPlaceholderStart) {
                    start -= selectedPlaceholderStart[0].length
                }
                if (selectedPlaceholderEnd) {
                    end += selectedPlaceholderEnd[0].length
                }

                lastFocusedInput.value =
                    content.substring(0, start) +
                    placeholderValue +
                    content.substring(end)
                lastFocusedInput.selectionStart = start
                lastFocusedInput.selectionEnd = start + placeholderValue.length
                lastFocusedInput.focus()
            }
        })
    })

    const drawer = document.querySelector("#placeholder-drawer")
    if (drawer) {
        const toggle = document.querySelector("[data-placeholder-toggle]")
        const search = document.querySelector("#placeholder-search")
        const empty = document.querySelector("#placeholder-empty")

        if (toggle) {
            toggle.addEventListener("click", () => {
                setDrawerOpen(drawer, toggle, search, drawer.hidden)
            })
        }
        document.querySelectorAll("[data-placeholder-close]").forEach((button) => {
            button.addEventListener("click", () => {
                setDrawerOpen(drawer, toggle, search, false)
            })
        })
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && !drawer.hidden) {
                setDrawerOpen(drawer, toggle, search, false)
                if (toggle) toggle.focus()
            }
        })
        if (search) {
            search.addEventListener("input", () => {
                filterPlaceholders(drawer, empty, search.value)
            })
        }
    }

    // The teams composer has no speaker filter, so these groups never change there.
    const speakerSelect = document.querySelector("#id_speakers")
    if (speakerSelect) {
        speakerSelect.addEventListener("change", () => {
            updateVisiblePlaceholders(speakerSelect)
        })
        updateVisiblePlaceholders(speakerSelect)
    }
})
