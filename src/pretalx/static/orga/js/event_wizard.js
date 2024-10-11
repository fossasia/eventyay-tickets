const number = new Date().getYear() + 1900
const updateSlug = (ev) => {
    const value = ev.target.value
    let slug = value.replace(/\W+/g, "-").toLowerCase()
    if (slug && slug.indexOf(number) == -1) slug += "-" + number
    if (slug) document.querySelector("#id_basics-slug").value = slug
}
onReady(() => {
    const i18nNameInputs = document.getElementById("id_basics-name_0").parentElement.querySelectorAll("input")
    i18nNameInputs.forEach((element) => {
        element.addEventListener("input", updateSlug)
    })
    document.querySelector("#id_basics-slug").addEventListener("input", (ev) => {
        i18nNameInputs.forEach((element) => {
            element.removeEventListener("input", updateSlug)
        })
    })
})
