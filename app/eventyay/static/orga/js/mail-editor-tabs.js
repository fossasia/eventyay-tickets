const getCsrfToken = (form) => {
    const input = form?.querySelector('input[name="csrfmiddlewaretoken"]')
    return input ? input.value : ''
}

const getActiveLocale = () => {
    const activeLanguageTab = document.querySelector(".mail-language-tab[aria-selected='true']")
    if (activeLanguageTab) {
        return activeLanguageTab.dataset.locale
    }
    const message = document.querySelector("#id_text textarea[lang], #id_message textarea[lang]")
    return message ? message.lang : ""
}

const getMessageHtml = (locale) => {
    const textarea = locale
        ? document.querySelector(`#id_text textarea[lang="${locale}"], #id_message textarea[lang="${locale}"]`)
        : document.querySelector("#id_text textarea[lang], #id_message textarea[lang]")
    return textarea ? textarea.value : ""
}

const showPreviewLocale = (panel, locale) => {
    panel.querySelectorAll(".mail-preview[lang]").forEach((preview) => {
        preview.hidden = Boolean(locale && preview.lang !== locale)
    })
}

const showPreviewError = (target) => {
    target.textContent = typeof window.gettext === "function"
        ? window.gettext("Preview could not be loaded.")
        : "Preview could not be loaded."
}

const replaceHtml = (target, html) => {
    const parsed = new DOMParser().parseFromString(html || "", "text/html")
    target.replaceChildren(...parsed.body.childNodes)
}

const loadPreview = async (wrapper, previewPanel, locale) => {
    const previewUrl = wrapper.dataset.emailPreviewUrl
    if (!previewUrl) {
        return
    }

    const previewBlock = previewPanel.querySelector(`.mail-preview[lang="${locale}"]`)
        || previewPanel.querySelector(".mail-preview")
    if (!previewBlock) {
        return
    }

    previewBlock.textContent = typeof window.gettext === "function"
        ? window.gettext("Loading preview…")
        : "Loading preview…"

    try {
        const response = await fetch(previewUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(wrapper.closest("form")),
            },
            credentials: "same-origin",
            body: JSON.stringify({
                html: getMessageHtml(locale),
                locale: locale || undefined,
            }),
        })
        if (!response.ok) {
            throw new Error(`Preview request failed: ${response.status}`)
        }
        const data = await response.json()
        replaceHtml(previewBlock, data.html)
    } catch (error) {
        console.error("Email preview failed:", error)
        showPreviewError(previewBlock)
    }
}

const initMailEditorTabs = () => {
    const wrapper = document.querySelector(".mail-editor-tabs")
    if (!wrapper) {
        return
    }

    const buttons = [...wrapper.querySelectorAll("[data-mail-editor-mode]")]
    const editPanel = wrapper.querySelector("#mail-message-edit")
    const previewPanel = wrapper.querySelector("#mail-message-preview")
    if (!buttons.length || !editPanel || !previewPanel) {
        return
    }

    let previewRequest = 0

    const selectMode = async (mode) => {
        const previewSelected = mode === "preview"
        buttons.forEach((button) => {
            const active = button.dataset.mailEditorMode === mode
            button.classList.toggle("active", active)
            button.setAttribute("aria-selected", active ? "true" : "false")
            button.tabIndex = active ? 0 : -1
        })
        wrapper.dataset.mailEditorActive = mode

        if (previewSelected) {
            const locale = getActiveLocale()
            showPreviewLocale(previewPanel, locale)
            const requestId = ++previewRequest
            editPanel.setAttribute("aria-hidden", "true")
            editPanel.hidden = true
            previewPanel.setAttribute("aria-hidden", "false")
            previewPanel.hidden = false
            await loadPreview(wrapper, previewPanel, locale)
            if (requestId !== previewRequest) {
                return
            }
        } else {
            previewRequest += 1
            editPanel.setAttribute("aria-hidden", "false")
            editPanel.hidden = false
            previewPanel.setAttribute("aria-hidden", "true")
            previewPanel.hidden = true
        }
    }

    buttons.forEach((button, index) => {
        button.addEventListener("click", () => {
            selectMode(button.dataset.mailEditorMode)
        })
        button.addEventListener("keydown", (event) => {
            const offset = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0
            if (!offset) {
                return
            }
            event.preventDefault()
            const next = buttons[(index + offset + buttons.length) % buttons.length]
            selectMode(next.dataset.mailEditorMode)
            next.focus()
        })
    })

    document.addEventListener("mail-language-change", (event) => {
        if (previewPanel.getAttribute("aria-hidden") === "true") {
            return
        }
        const locale = event.detail.locale
        showPreviewLocale(previewPanel, locale)
        loadPreview(wrapper, previewPanel, locale)
    })

    selectMode("edit")
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMailEditorTabs)
} else {
    initMailEditorTabs()
}
