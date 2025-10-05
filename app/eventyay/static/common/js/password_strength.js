const matchPasswords = (passwordField, confirmationFields) => {
    // Optional parameter: if no specific confirmation field is given, check all
    if (confirmationFields === undefined) {
        confirmationFields = document.querySelectorAll(".password_confirmation")
    }
    if (confirmationFields === undefined) return

    const password = passwordField.value

    confirmationFields.forEach((confirmationField, index) => {
        const confirmValue = confirmationField.value
        const confirmWith = confirmationField.dataset.confirmWith

        if (confirmWith && confirmWith === passwordField.name) {
            if (confirmValue && password) {
                if (confirmValue === password) {
                    confirmationField.parentNode
                        .querySelector(".password_strength_info")
                        .classList.add("d-none")
                } else {
                    confirmationField.parentNode
                        .querySelector(".password_strength_info")
                        .classList.remove("d-none")
                }
            } else {
                confirmationField.parentNode
                    .querySelector(".password_strength_info")
                    .classList.add("d-none")
            }
        }
    })

    // If a password field other than our own has been used, add the listener here
    if (
        !passwordField.classList.contains("password_strength") &&
        !passwordField.dataset.passwordListener
    ) {
        passwordField.addEventListener("keyup", () =>
            matchPasswords(passwordField),
        )
        passwordField.dataset.passwordListener = true
    }
}

const updatePasswordStrength = (passwordField) => {
    const passwordStrengthBar = passwordField.parentNode.querySelector(
        ".password_strength_bar",
    )
    const passwordStrengthInfo = passwordField.parentNode.querySelector(
        ".password_strength_info",
    )

    if (!passwordField.value) {
        passwordStrengthBar.classList.remove("bg-success")
        passwordStrengthBar.classList.add("bg-warning")
        passwordStrengthBar.style.width = "0%"
        passwordStrengthBar.setAttribute("aria-valuenow", 0)
        passwordStrengthInfo.classList.add("d-none")
    } else {
        const result = zxcvbn(passwordField.value)
        const crackTime =
            result.crack_times_display.online_no_throttling_10_per_second

        if (result.score < 1) {
            passwordStrengthBar.classList.remove("bg-success")
            passwordStrengthBar.classList.add("bg-danger")
        } else if (result.score < 3) {
            passwordStrengthBar.classList.remove("bg-danger")
            passwordStrengthBar.classList.add("bg-warning")
        } else {
            passwordStrengthBar.classList.remove("bg-warning")
            passwordStrengthBar.classList.add("bg-success")
        }

        passwordStrengthBar.style.width = `${((result.score + 1) / 5) * 100}%`
        passwordStrengthBar.setAttribute("aria-valuenow", result.score + 1)
        passwordStrengthInfo.querySelector(
            ".password_strength_time",
        ).innerHTML = crackTime
        passwordStrengthInfo.classList.remove("d-none")
    }
    matchPasswords(passwordField)
}

const setupPasswordStrength = () => {
    document.querySelectorAll(".password_strength_info").forEach((element) => {
        element.classList.add("d-none")
    })
    document.querySelectorAll(".password_strength").forEach((passwordField) => {
        passwordField.addEventListener("keyup", () =>
            updatePasswordStrength(passwordField),
        )
    })

    let timer = null
    document
        .querySelectorAll(".password_confirmation")
        .forEach((confirmationField) => {
            confirmationField.addEventListener("keyup", () => {
                let passwordField
                const confirmWith = confirmationField.dataset.confirmWith

                if (confirmWith) {
                    passwordField = document.querySelector(
                        `[name=${confirmWith}]`,
                    )
                } else {
                    passwordField = document.querySelector(".password_strength")
                }

                if (timer !== null) clearTimeout(timer)
                timer = setTimeout(() => matchPasswords(passwordField), 400)
            })
        })
}

onReady(setupPasswordStrength)
