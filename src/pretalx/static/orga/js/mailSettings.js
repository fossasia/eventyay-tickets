const dependents = ["mail_from", "smtp_host", "smtp_port", "smtp_username", "smtp_password"]
const checkboxDependents = ["smtp_use_tls", "smtp_use_ssl"]
const updateVisibility = () => {

  if (document.querySelector("input#id_smtp_use_custom").checked) {
    dependents.forEach(element => document.querySelector(`#id_${element}`).parentElement.parentElement.classList.remove("d-none"))
    checkboxDependents.forEach(element => document.querySelector(`#id_${element}`).parentElement.parentElement.parentElement.classList.remove("d-none"))
    document.querySelector("button[name=test]").disabled = false
  } else {
    dependents.forEach(element => document.querySelector(`#id_${element}`).parentElement.parentElement.classList.add("d-none"))
    checkboxDependents.forEach(element => document.querySelector(`#id_${element}`).parentElement.parentElement.parentElement.classList.add("d-none"))
    document.querySelector("button[name=test]").disabled = true
  }
}
document.querySelector("input#id_smtp_use_custom").addEventListener("change", (event) => {updateVisibility()})
updateVisibility()
