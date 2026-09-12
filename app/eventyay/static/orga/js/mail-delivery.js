/* Switches the Delivery section between sending immediately and scheduling,
 * keeping the scheduled time inputs hidden and empty unless they apply. */

const setDeliveryMode = (schedule, scheduled) => {
    schedule.hidden = !scheduled
    if (!scheduled) {
        schedule.querySelectorAll("input").forEach((input) => {
            input.value = ""
        })
    }
}

const initDeliveryMode = () => {
    const schedule = document.querySelector("#delivery-schedule")
    const now = document.querySelector("#delivery-mode-now")
    const later = document.querySelector("#delivery-mode-later")
    if (!schedule || !now || !later) return

    const hasValue = [...schedule.querySelectorAll("input")].some((input) => input.value)
    if (hasValue) {
        later.checked = true
    }
    setDeliveryMode(schedule, later.checked)

    now.addEventListener("change", () => setDeliveryMode(schedule, false))
    later.addEventListener("change", () => setDeliveryMode(schedule, true))
}

const initTestEmailValidation = () => {
    const testButton = document.querySelector('button[name="action"][value="test"]')
    if (!testButton) return

    testButton.addEventListener("click", (e) => {
        const form = testButton.closest("form")
        const emailInput = form.querySelector("#id_test_email")
        if (!emailInput) return

        const emailValue = emailInput.value.trim()
        let isValid = true
        let errorMessage = ""

        if (!emailValue) {
            isValid = false
            errorMessage = testButton.dataset.errorEmpty || "Please enter an email address to send the test email."
        } else {
            // basic email regex validation
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
            if (!emailRegex.test(emailValue)) {
                isValid = false
                errorMessage = testButton.dataset.errorInvalid || "Please enter a valid email address."
            }
        }

        const container = emailInput.closest(".col-md-9")
        if (!isValid) {
            e.preventDefault()
            emailInput.classList.add("is-invalid")
            emailInput.setAttribute("aria-invalid", "true")

            if (container) {
                container.querySelectorAll(".invalid-feedback").forEach(el => el.remove())

                const errorDiv = document.createElement("div")
                errorDiv.className = "invalid-feedback d-block"
                errorDiv.textContent = errorMessage
                
                const controls = container.querySelector(".delivery-test-controls")
                if (controls) {
                    controls.insertAdjacentElement("afterend", errorDiv)
                }
            }
        } else {
            emailInput.classList.remove("is-invalid")
            emailInput.removeAttribute("aria-invalid")
            if (container) {
                container.querySelectorAll(".invalid-feedback").forEach(el => el.remove())
            }
        }
    })
    
    const emailInput = document.querySelector("#id_test_email")
    if (emailInput) {
        emailInput.addEventListener("input", () => {
            emailInput.classList.remove("is-invalid")
            emailInput.removeAttribute("aria-invalid")
            const container = emailInput.closest(".col-md-9")
            if (container) {
                container.querySelectorAll(".invalid-feedback").forEach(el => el.remove())
            }
        })
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initDeliveryMode()
        initTestEmailValidation()
    })
} else {
    initDeliveryMode()
    initTestEmailValidation()
}
