const dependents = [
    "mail_from",
    "smtp_host",
    "smtp_port",
    "smtp_username",
    "smtp_password",
    "smtp_use_tls",
    "smtp_use_ssl",
]
const smtpInput = document.querySelector("input#id_smtp_use_custom")
const updateVisibility = () => {
    const showCustomSettings = smtpInput.checked
    dependents.forEach((element) =>
        document.querySelector(`#id_${element}`).closest(".form-group").classList.toggle("d-none", !showCustomSettings),
    )
    document.querySelector("button[name=test]").disabled = !showCustomSettings
}
onReady(() => {
    smtpInput.addEventListener("change", updateVisibility)
    updateVisibility()
})
