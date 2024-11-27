const initAvailabilities = (element) => {
    const data = JSON.parse(element.getAttribute("value"))

    const editor = document.createElement("div")
    editor.classList.add("availabilities-editor")

    editor.setAttribute("data-name", element.getAttribute("name"))
    element.insertAdjacentElement("afterend", editor)
    editor.insertAdjacentHTML(
        "beforebegin",
        `<div class="availabilities-tz-hint">${data.event.timezone}</div>`,
    )

    const save_events = () => {
        const data = {
            availabilities: calendar
                .getEvents()
                .map(function (e) {
                    if (e.groupId) return
                    if (e.allDay) {
                        return {
                            start: moment(e.start).format(
                                "YYYY-MM-DD HH:mm:ss",
                            ),
                            end: moment(e.end).format("YYYY-MM-DD HH:mm:ss"),
                        }
                    } else {
                        return {
                            start: e.start.toISOString(),
                            end: e.end.toISOString(),
                        }
                    }
                })
                .filter((a) => !!a),
        }
        element.setAttribute("value", JSON.stringify(data))
    }

    const editable = !Boolean(element.getAttribute("disabled"))
    const constraints = data.constraints || null

    const slotDuration = data.resolution || "00:30:00"
    let events = data.availabilities.map((e) => {
        const start = moment(e.start)
        const end = moment(e.end)
        if (start.format("HHmmss") == 0 && end.format("HHmmss") == 0) {
            e.allDay = true
        }
        e.start = start.toISOString()
        e.end = end.toISOString()
        if (constraints) {
            e.constraint = "mainConstraint"
        }
        return e
    })
    if (constraints) {
        for (constraint of constraints) {
            events.push({
                start: constraint.start,
                end: constraint.end,
                groupId: "mainConstraint",
                display: "background",
            })
        }
    }
    const localeData = document.querySelector("#calendar-locale")
    const locale = localeData ? localeData.dataset.locale : "en"
    const calendar = new FullCalendar.Calendar(editor, {
        timeZone: data.event.timezone,
        locale: locale,
        initialView: "timeGrid",
        initialDate: data.event.date_from,
        duration: {
            days:
                moment(data.event.date_to).diff(
                    moment(data.event.date_from),
                    "days",
                ) + 1,
        },
        headerToolbar: false,
        events: events,
        slotDuration: slotDuration,
        slotLabelFormat: {
            hour: "numeric",
            minute: "2-digit",
            omitZeroMinute: false,
            hour12: false,
        },
        eventTimeFormat: {
            hour: "numeric",
            minute: "2-digit",
            omitZeroMinute: false,
            hour12: false,
        },
        scrollTime: "09:00:00",
        selectable: editable,
        editable: editable,
        eventStartEditable: editable,
        eventDurationEditable: editable,
        allDayMaintainDuration: true,
        eventsSet: save_events,
        eventColor: "#2185d0",
        eventConstraint: constraints ? "mainConstraint" : null,
        eventOverlap: !!constraints, // we can't use element with constraints, because those are also only background events
        selectOverlap: !!constraints, // we have to set element, otherwise events can only be created *outside* our available times
        selectConstraint: constraints ? "mainConstraint" : null,
        select: function (info) {
            if (
                document.querySelector(
                    ".availabilities-editor .fc-event.delete",
                )
            ) {
                document
                    .querySelectorAll(".availabilities-editor .fc-event.delete")
                    .forEach(function (e) {
                        e.classList.remove("delete")
                    })
                return
            }
            const eventData = {
                start: info.start,
                end: info.end,
                constraint: constraints ? "mainConstraint" : null,
            }
            calendar.addEvent(eventData)
            calendar.unselect()
        },
        eventClick: function (info) {
            if (!editable || info.el.classList.contains("fc-bg-event")) {
                return
            }
            if (info.el.classList.contains("delete")) {
                info.event.remove()
                save_events()
            } else {
                info.el.classList.add("delete")
            }
        },
    })
    // initialDate is not respected, so we have to set it manually
    calendar.gotoDate(data.event.date_from)
    calendar.render()
    // not sure why the calendar doesn't render properly without element. Has to be in a timeout, though!
    setTimeout(() => {
        calendar.updateSize()
    }, 20)
}

onReady(() => {
    document
        .querySelectorAll("input.availabilities-editor-data")
        .forEach((element) => initAvailabilities(element))
})
