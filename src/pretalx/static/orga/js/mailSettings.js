const dependents = ["mail_from", "smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_use_tls", "smtp_use_ssl"]
const updateVisibility = () => {

  if (document.querySelector("input#id_smtp_use_custom").checked) {
    dependents.forEach(element => document.querySelector(`#id_${element}`).parentElement.parentElement.classList.remove("d-none"))
  } else {
    dependents.forEach(element => document.querySelector(`#id_${element}`).parentElement.parentElement.classList.add("d-none"))
  }
}
document.querySelector("input#id_smtp_use_custom").addEventListener("change", (event) => {updateVisibility()})
updateVisibility()
