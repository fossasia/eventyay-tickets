/* Keeps the audience summary in step with the recipient filters, and fills the
 * recipient list dialog from the same endpoint the send path filters on. */

const MESSAGE_FIELDS = /^(csrfmiddlewaretoken|action|subject_|text_|reply_to|bcc|scheduled_at|delivery_mode|skip_queue|test_email|attachment)/

// Filters the composer was opened with live in the page URL rather than in the
// form, so they have to be carried over separately.
const URL_FILTER_KEYS = ["q", "question", "answer", "answer__options", "unanswered"]

const buildFilterQuery = (form) => {
    const params = new URLSearchParams()
    new FormData(form).forEach((value, key) => {
        if (MESSAGE_FIELDS.test(key) || value instanceof File || value === "") {
            return
        }
        params.append(key, value)
    })
    const pageParams = new URLSearchParams(window.location.search)
    URL_FILTER_KEYS.forEach((key) => {
        const value = pageParams.get(key)
        if (value && !params.has(key)) {
            params.append(key, value)
        }
    })
    return params
}

/**
 * @throws {Error} when the recipient endpoint is unreachable or refuses the request
 */
const fetchRecipients = async (url, form) => {
    const response = await fetch(`${url}?${buildFilterQuery(form)}`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
    })
    if (!response.ok) {
        let detail = ""
        try {
            const payload = await response.json()
            detail = payload && payload.error ? ` ${JSON.stringify(payload.error)}` : ""
        } catch {
            // Response body is not JSON; status alone is enough for the log.
        }
        throw new Error(`Recipient lookup failed with status ${response.status}${detail}`)
    }
    return response.json()
}

// A composer opts into refusing an empty audience with data-requires-audience on
// its summary, and names the empty state with data-label-none. Composers that
// carry neither keep counting to zero and leave their send actions alone.
const SEND_ACTIONS =
    'button[name="action"][value="send"], button[name="action"][value="draft"], [data-send-option="now"], [data-send-option="schedule"]'

const renderCount = (el, count) => {
    if (count < 1 && el.dataset.labelNone) {
        el.textContent = el.dataset.labelNone
        el.hidden = false
        return
    }
    const label = count === 1 ? el.dataset.labelOne : el.dataset.labelOther
    el.textContent = `${count} ${label}`
    // Audience badge stays quiet until there is an audience; footer summary always shows.
    if (el.id === "recipient-count") {
        el.hidden = count < 1
    } else {
        el.hidden = false
    }
}

const setSendingEnabled = (form, enabled) => {
    form.querySelectorAll(SEND_ACTIONS).forEach((control) => {
        control.disabled = !enabled
    })
    // The caret of the split send button is a <summary>, which cannot be disabled and
    // stays focusable, so the state has to be announced rather than only dimmed.
    const moreOptions = form.querySelector(".composer-send-group details.dropdown")
    if (moreOptions) {
        const caret = moreOptions.querySelector("summary")
        caret.classList.toggle("disabled", !enabled)
        caret.setAttribute("aria-disabled", String(!enabled))
        if (!enabled) moreOptions.open = false
    }
    if (!enabled) {
        // A dialog opened just before the count arrived would still offer an audience
        // that has since gone, behind a send button that no longer works.
        const confirmDialog = form.querySelector("#send-confirm-dialog")
        if (confirmDialog && confirmDialog.open) confirmDialog.close()
    }
}

const clearFilters = (form) => {
    const filters = form.querySelector(".composer-filters")
    if (!filters) return
    // Choices keeps its own state and ignores the underlying select, so drop the
    // selections through the remove buttons it renders. It acts on mousedown,
    // which click() does not fire.
    const nextButton = () => filters.querySelector(".choices__list--multiple .choices__button")
    let button = nextButton()
    let guard = 0
    while (button && guard < 500) {
        button.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }))
        button = nextButton()
        guard += 1
    }
    filters.querySelectorAll("select.enhanced").forEach((select) => {
        // On a multiple select, selectedIndex = 0 selects the first option
        // rather than clearing the field.
        if (select.multiple) {
            Array.from(select.options).forEach((option) => {
                option.selected = false
            })
        } else {
            select.selectedIndex = 0
        }
        if (select.choices) {
            if (select.multiple) {
                select.choices.removeActiveItems()
            } else {
                select.choices.setChoiceByValue("")
            }
        }
        select.dispatchEvent(new Event("change", { bubbles: true }))
    })
    if (window.jQuery) {
        filters.querySelectorAll("select[data-model-select2], select.select2-hidden-accessible").forEach((select) => {
            window.jQuery(select).val(null).trigger("change")
        })
    }
    filters.querySelectorAll('input[type="date"], input[type="time"], input[type="text"]').forEach((input) => {
        input.value = ""
        input.dispatchEvent(new Event("change", { bubbles: true }))
    })
    filters.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
        checkbox.checked = false
        checkbox.dispatchEvent(new Event("change", { bubbles: true }))
    })
}

const renderRecipients = (body, recipients) => {
    body.replaceChildren()
    const listData = Array.isArray(recipients) ? recipients : []
    if (!listData.length) {
        const empty = document.createElement("p")
        empty.className = "text-muted"
        empty.textContent = body.dataset.emptyLabel
        body.appendChild(empty)
        return
    }
    const list = document.createElement("ul")
    list.className = "list-group list-group-flush"
    listData.forEach((recipient) => {
        const item = document.createElement("li")
        item.className = "list-group-item"
        const name = document.createElement("strong")
        name.textContent = recipient.name || recipient.email || ""
        const email = document.createElement("span")
        email.className = "text-muted ml-2"
        email.textContent = recipient.email || ""
        item.append(name, email)
        ;(recipient.submissions || []).forEach((submission) => {
            const line = document.createElement("div")
            line.className = "text-muted"
            line.textContent = `${submission.title} (${submission.state})`
            item.appendChild(line)
        })
        if (recipient.directly_selected) {
            const line = document.createElement("div")
            line.className = "text-muted"
            line.textContent = body.dataset.directLabel
            item.appendChild(line)
        }
        list.appendChild(item)
    })
    body.appendChild(list)
}

const initRecipientPreview = () => {
    const trigger = document.querySelector("#show-recipient-list")
    const badge = document.querySelector("#recipient-count")
    const body = document.querySelector("#recipient-list-body")
    if (!trigger || !badge || !body) return

    const form = trigger.closest("form")
    const url = trigger.dataset.recipientsUrl
    if (!form || !url) {
        console.error("Recipient preview is missing form or endpoint URL")
        return
    }

    const summary = document.querySelector("#recipient-summary")
    const requiresAudience = Boolean(summary && "requiresAudience" in summary.dataset)

    // Responses can arrive out of order, and a stale one would report an audience
    // the form no longer has, re-enabling the send buttons.
    let latestRequest = 0

    const applyCount = (count) => {
        renderCount(badge, count)
        if (summary) renderCount(summary, count)
        if (requiresAudience) setSendingEnabled(form, count > 0)
    }

    // The audience has just changed, so any answer already in flight describes the
    // old one, and the new count is not known until it arrives.
    const invalidateCount = () => {
        latestRequest += 1
        if (requiresAudience) setSendingEnabled(form, false)
    }

    const refreshCount = async () => {
        const request = (latestRequest += 1)
        try {
            const data = await fetchRecipients(url, form)
            if (request !== latestRequest) return
            applyCount(data.count)
        } catch (error) {
            if (request !== latestRequest) return
            console.error("Could not refresh the recipient count", error)
            badge.hidden = true
            if (summary) {
                summary.textContent = summary.dataset.labelUnavailable || ""
            }
            // The count is unknown, so let the server-side check decide instead.
            if (requiresAudience) setSendingEnabled(form, true)
        }
    }

    const clearButton = document.querySelector("#clear-filters")
    if (clearButton) {
        clearButton.addEventListener("click", () => {
            clearFilters(form)
            invalidateCount()
            window.clearTimeout(timer)
            timer = window.setTimeout(refreshCount, 50)
        })
    }

    let timer = null
    form.addEventListener("change", (e) => {
        if (MESSAGE_FIELDS.test(e.target.name || "")) return
        invalidateCount()
        window.clearTimeout(timer)
        timer = window.setTimeout(refreshCount, 300)
    })

    trigger.addEventListener("click", async () => {
        body.textContent = body.dataset.loadingLabel
        const request = (latestRequest += 1)
        try {
            const data = await fetchRecipients(url, form)
            if (request === latestRequest) applyCount(data.count)
            renderRecipients(body, data.recipients)
        } catch (error) {
            console.error("Could not load the recipient list", error)
            body.textContent = body.dataset.errorLabel
        }
    })

    document.querySelectorAll("[data-recipient-close]").forEach((button) => {
        button.addEventListener("click", () => {
            document.querySelector("#recipient-list-dialog").close()
        })
    })

    refreshCount()
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initRecipientPreview)
} else {
    initRecipientPreview()
}
