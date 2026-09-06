/* Asks the organiser to confirm before a composed email goes out, summarising
 * who receives it, what it says and when it is sent. */

const addSummaryRow = (list, label, value) => {
    const term = document.createElement("dt")
    term.textContent = label
    const definition = document.createElement("dd")
    definition.textContent = value
    list.append(term, definition)
}

const getFilledLanguages = (form) => {
    const languages = []
    form.querySelectorAll('input[id^="id_subject_"], textarea[id^="id_text_"], textarea[id^="id_message_"]').forEach((field) => {
        const label = field.title || field.lang
        if (field.value.trim() && label && !languages.includes(label)) {
            languages.push(label)
        }
    })
    return languages
}

const isScheduled = (form) => {
    const later = form.querySelector("#delivery-mode-later")
    return Boolean(later && later.checked)
}

const getSendTimeLabel = (form, labels) => {
    const date = form.querySelector("#id_scheduled_at_0")
    const time = form.querySelector("#id_scheduled_at_1")
    if (!date || !time || !date.value || !time.value) return labels.labelMissing
    // Read and format as UTC: the inputs are a wall clock in the event timezone,
    // and going through the browser timezone shifts times that fall in its DST gap.
    const when = new Date(`${date.value}T${time.value}Z`)
    if (Number.isNaN(when.getTime())) return `${date.value} ${time.value}`
    const stamp = when.toLocaleString(document.documentElement.lang || undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZone: "UTC",
    })
    return labels.timezone ? `${stamp}, ${labels.timezone}` : stamp
}

const buildSendSummary = (summary, form) => {
    summary.replaceChildren()
    const labels = summary.dataset

    const badge = document.querySelector("#recipient-count")
    if (badge && !badge.hidden) {
        addSummaryRow(summary, labels.labelAudience, badge.textContent)
    }
    const type = document.querySelector("#composer-type")
    if (type && type.textContent.trim()) {
        addSummaryRow(summary, labels.labelType, type.textContent.trim())
    }
    const subject = [...form.querySelectorAll('input[id^="id_subject_"]')]
        .map((input) => input.value.trim())
        .find((value) => value)
    addSummaryRow(summary, labels.labelSubject, subject || labels.labelMissing)

    const languages = getFilledLanguages(form)
    if (languages.length) {
        addSummaryRow(summary, labels.labelLanguages, languages.join(", "))
    }
    if (isScheduled(form)) {
        addSummaryRow(summary, labels.labelSendTime, getSendTimeLabel(form, labels))
    } else {
        const nowLabel = form.querySelector('label[for="delivery-mode-now"]')
        if (nowLabel) {
            addSummaryRow(summary, labels.labelDelivery, nowLabel.textContent.trim())
        }
    }
}

const applyScheduleWording = (form) => {
    const scheduled = isScheduled(form)
    const skipQueue = form.querySelector("#id_skip_queue")
    const immediate = skipQueue && skipQueue.checked
    const title = document.querySelector("#send-confirm-title")
    const submit = document.querySelector("#send-confirm-submit")
    if (title) {
        if (scheduled) {
            title.textContent = title.dataset.titleSchedule
        } else if (immediate) {
            title.textContent = title.dataset.titleSendImmediate
        } else {
            title.textContent = title.dataset.titleSend
        }
    }
    if (submit) {
        if (scheduled) {
            submit.textContent = submit.dataset.labelSchedule
        } else if (immediate) {
            submit.textContent = submit.dataset.labelSendImmediate
        } else {
            submit.textContent = submit.dataset.labelSend
        }
    }
}

const chooseSendOption = (form, option) => {
    const now = form.querySelector("#delivery-mode-now")
    const later = form.querySelector("#delivery-mode-later")
    if (option === "test") {
        const address = form.querySelector("#id_test_email")
        if (address) {
            address.scrollIntoView({ block: "center" })
            address.focus()
        }
        return false
    }
    const target = option === "schedule" ? later : now
    if (target && !target.checked) {
        target.checked = true
        target.dispatchEvent(new Event("change", { bubbles: true }))
    }
    return true
}

const initSendConfirm = () => {
    const dialog = document.querySelector("#send-confirm-dialog")
    const trigger = document.querySelector("[data-confirm-send]")
    const summary = document.querySelector("#send-confirm-summary")
    if (!dialog || !trigger || !summary || typeof dialog.showModal !== "function") return

    const form = trigger.closest("form")
    const openDialog = () => {
        buildSendSummary(summary, form)
        applyScheduleWording(form)
        dialog.showModal()
    }

    trigger.addEventListener("click", (e) => {
        e.preventDefault()
        openDialog()
    })
    dialog.querySelectorAll("[data-confirm-cancel]").forEach((button) => {
        button.addEventListener("click", () => dialog.close())
    })
    form.querySelectorAll("[data-send-option]").forEach((button) => {
        button.addEventListener("click", () => {
            const dropdown = button.closest("details.dropdown")
            if (dropdown) dropdown.open = false
            if (chooseSendOption(form, button.dataset.sendOption)) {
                openDialog()
            }
        })
    })

    const skipQueue = form.querySelector("#id_skip_queue")
    const mainButtonLabel = form.querySelector("#main-send-button-label")
    if (skipQueue && mainButtonLabel) {
        const updateMainButton = () => {
            if (skipQueue.checked) {
                mainButtonLabel.textContent = mainButtonLabel.dataset.labelImmediate || "Send email"
            } else {
                mainButtonLabel.textContent = mainButtonLabel.dataset.labelOutbox || "Send to Outbox"
            }
        }
        skipQueue.addEventListener("change", updateMainButton)
        updateMainButton()
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSendConfirm)
} else {
    initSendConfirm()
}
