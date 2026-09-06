/* Shows one language version of the email at a time: the subject and text
 * fields both follow the language selected in the Message header. */

const LANGUAGE_INPUT_SELECTOR = "input[lang], textarea[lang]"

const getLocales = (group) => {
    const locales = []
    group.querySelectorAll(LANGUAGE_INPUT_SELECTOR).forEach((input) => {
        if (!locales.some((locale) => locale.code === input.lang)) {
            locales.push({ code: input.lang, label: input.title || input.lang })
        }
    })
    return locales
}

const toggleLocaleField = (input, hidden) => {
    input.classList.toggle("d-none", hidden)
    const wrapper = input.closest(".tiptap-wrapper")
    if (wrapper) {
        wrapper.classList.toggle("d-none", hidden)
    }
}

const showLocale = (groups, tabs, code) => {
    groups.forEach((group) => {
        group.querySelectorAll(LANGUAGE_INPUT_SELECTOR).forEach((input) => {
            toggleLocaleField(input, input.lang !== code)
        })
    })
    tabs.forEach((tab) => {
        const active = tab.dataset.locale === code
        tab.classList.toggle("active", active)
        tab.setAttribute("aria-selected", active ? "true" : "false")
        tab.tabIndex = active ? 0 : -1
    })
    document.dispatchEvent(new CustomEvent("mail-language-change", { detail: { locale: code } }))
}

const buildLanguageTabs = (container, groups) => {
    const locales = getLocales(groups[0])
    if (locales.length < 2) return

    const tabs = locales.map((locale) => {
        const tab = document.createElement("button")
        tab.type = "button"
        tab.className = "btn btn-link mail-language-tab"
        tab.dataset.locale = locale.code
        tab.setAttribute("role", "tab")
        tab.textContent = locale.label
        container.appendChild(tab)
        return tab
    })

    tabs.forEach((tab, index) => {
        tab.addEventListener("click", () => showLocale(groups, tabs, tab.dataset.locale))
        tab.addEventListener("keydown", (e) => {
            const offset = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0
            if (!offset) return
            e.preventDefault()
            const next = tabs[(index + offset + tabs.length) % tabs.length]
            showLocale(groups, tabs, next.dataset.locale)
            next.focus()
        })
    })

    container.setAttribute("role", "tablist")
    container.hidden = false
    showLocale(groups, tabs, locales[0].code)
}

const initLanguageTabs = () => {
    const container = document.querySelector("#mail-language-tabs")
    if (!container) return
    const groups = [
        document.querySelector("#id_subject"),
        document.querySelector("#id_text"), document.querySelector("#id_message"),
    ].filter((group) => group)
    if (groups.length) {
        buildLanguageTabs(container, groups)
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLanguageTabs)
} else {
    initLanguageTabs()
}
