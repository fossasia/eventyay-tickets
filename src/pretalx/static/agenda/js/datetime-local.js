const utcoffset = new Date().getTimezoneOffset()
const FORMAT_ARGS = { hour: "numeric", minute: "2-digit" }

const addLocalTimeRange = (element) => {
    const start = element.querySelector("time[datetime]")
    const end = element.querySelector("time[datetime]:last-of-type")

    const startDate = moment(start.dataset.isodatetime)
    const endDate = moment(end.dataset.isodatetime)
    if (startDate.format() === start.dataset.isodatetime) {
        // same timezone
        return
    }
    const startString = startDate.format("HH:mm")
    const endString = endDate.format("HH:mm")
    console.log(startDate)
    const tzString = moment.tz.guess()
    const helpText = document.createElement("span")
    helpText.classList.add("timezone-help")
    helpText.innerHTML = `<i class="fa fa-globe"></i> ${startString}-${endString} (${tzString})`
    // insert inside the timerange block
    element.appendChild(helpText)
}

const addLocalTime = (element) => {
    const elementOffset = getOffset(element)
    if (elementOffset === utcoffset) {
        return
    }
    const date = new Date(element.getAttribute("datetime"))
    const localString = date.toLocaleString(undefined, FORMAT_ARGS)
    const helpText = document.createElement("span")
    const tzString = getTzString(date)
    helpText.classList.add("timezone-help")
    helpText.innerHTML = `<i class="fa fa-globe"></i> ${localString} (${tzString})`
    // insert next to the time element
    element.insertAdjacentElement("afterend", helpText)
}

onReady(() => {
    document.querySelectorAll("time[datetime]").forEach((element) => {
        if (!element.parentElement.classList.contains("timerange-block")) {
            addLocalTime(element)
        }
    })
    document.querySelectorAll(".timerange-block").forEach((element) => {
        addLocalTimeRange(element)
    })
})
