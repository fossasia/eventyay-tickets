document.addEventListener("DOMContentLoaded", function() {

  $("input.availabilities-editor-data").each(function() {
    const data_field = $(this)
    const data = JSON.parse(data_field.attr("value"))

    var editor = $('<div class="availabilities-editor">')
    editor.attr("data-name", data_field.attr("name"))
    data_field.after(editor)
    editor.before($(`<div class="availabilities-tz-hint">${data.event.timezone}</div>`))

    function save_events() {
      data = {
        availabilities: calendar.getEvents().map(function(e) {
          if (e.allDay) {
            return {
              start: e.start.format("YYYY-MM-DD HH:mm:ss"),
              end: e.end.format("YYYY-MM-DD HH:mm:ss"),
            }
          } else {
            return {
              start: e.start.toISOString(),
              end: e.end.toISOString(),
            }
          }
        }),
      }
      data_field.attr("value", JSON.stringify(data))
    }

    var editable = !Boolean(data_field.attr("disabled"))
    const constraints = data.constraints || null

    const slotDuration = data.resolution || "00:30:00"
    var events = data.availabilities.map(function(e) {
      const start = moment(e.start)
      const end = moment(e.end)
      if (start.format("HHmmss") == 0 && end.format("HHmmss") == 0) {
        e.allDay = true
      }
      e.start = start.toISOString()
      e.end = end.toISOString()
      return e
    })
    let localeData = document.querySelector("#calendar-locale")
    const locale = localeData ? localeData.dataset.locale : "en"
    console.log(data)
    const calendar = new FullCalendar.Calendar(editor[0], {
      timeZone: data.event.timezone,
      locale: locale,
      initialView: 'timeGrid',
      headerToolbar: {},
      initialDate: data.event.date_from,
      duration: {
        days: moment(data.event.date_to).diff(moment(data.event.date_from), 'days') + 1,
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
      selectOverlap: false,
      eventOverlap: false,
      allDayMaintainDuration: true,
      eventsSet: save_events,
      eventColor: "#3aa57c",
      eventConstraint: constraints,
      selectConstraint: constraints,
      businessHours: constraints,
      select: function(info) {
        if (document.querySelector(".availabilities-editor .fc-event.delete")) {
          document.querySelectorAll(".availabilities-editor .fc-event.delete").forEach(function(e) { e.classList.remove("delete") })
          return
        }
        const eventData = {
          start: info.start,
          end: info.end,
        }
        calendar.addEvent(eventData)
        calendar.unselect()
      },
      eventClick: function(info) {
        if (!editable) {
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
    // not sure why the calendar doesn't render properly without this. Has to be in a timeout, though!
    setTimeout(function() {calendar.updateSize() }, 20)
  })
})
