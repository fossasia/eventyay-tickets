const dateFormat = $("body").attr("data-dateformat")

const setDates = (picker) => {
  const minDate = $(picker).attr("data-date-start-date")
  const maxDate = $(picker).attr("data-date-end-date")
  if (minDate) $(picker).data("DateTimePicker").minDate(moment(minDate, dateFormat))
  if (maxDate) $(picker).data("DateTimePicker").maxDate(moment(maxDate, dateFormat))
}

const activateDateTimePicker = (field) => {
    $(field).datetimepicker({
      format: $("body").attr("data-datetimeformat"),
      locale: $("body").attr("data-datetimelocale"),
      useCurrent: false,
      showClear: !$(field).prop("required"),
      icons: {
        time: "fa fa-clock-o",
        date: "fa fa-calendar",
        up: "fa fa-chevron-up",
        down: "fa fa-chevron-down",
        previous: "fa fa-chevron-left",
        next: "fa fa-chevron-right",
        today: "fa fa-image",
        clear: "fa fa-trash",
        close: "fa fa-times",
      },
    })
    setDates(field)
}

const activateDatePicker = (field) => {
    var opts = {
      format: $("body").attr("data-dateformat"),
      locale: $("body").attr("data-datetimelocale"),
      useCurrent: false,
      showClear: !$(field).prop("required"),
      icons: {
        time: "fa fa-clock-o",
        date: "fa fa-calendar",
        up: "fa fa-chevron-up",
        down: "fa fa-chevron-down",
        previous: "fa fa-chevron-left",
        next: "fa fa-chevron-right",
        today: "fa fa-image",
        clear: "fa fa-trash",
        close: "fa fa-times",
      },
    }
    $(field).datetimepicker(opts)
    setDates(field)
}

$(function() {
  $(".datetimepickerfield").each(function() {
      activateDateTimePicker(this)
  })

  $(".datepickerfield").each(function() {
      activateDatePicker(this)
  })

  $(".datetimepickerfield[data-date-after], .datepickerfield[data-date-after], .datetimepickerfield[data-date-before], .datepicker[data-date-after]").each(
    function() {
      const field = $(this)
      let relatedDateAfter = $(this).attr("data-date-after")
      let relatedDateBefore = $(this).attr("data-date-before")
      const dateAfter = $(this).attr("data-date-start-date")
      const dateBefore = $(this).attr("data-date-end-date")

      const updateStart = () => {
        const current = field.data("DateTimePicker").date()
        let earlier = relatedDateAfter.val()

        if (earlier) {
          earlier = moment(earlier, $("body").attr("data-dateformat"))
        } else {
          earlier = dateAfter
        }
        if (dateAfter && earlier) {
          earlier = (moment(earlier, $("body").attr("data-dateformat")).isBefore(moment(dateAfter)) ? dateAfter : earlier)
        }
        if (
          current !== null &&
          current.isBefore(earlier) &&
          !current.isSame(earlier)
        ) {
          field.data("DateTimePicker").date(earlier.add(1, "h"))
        }
        field.data("DateTimePicker").minDate(earlier)
      }
      const updateEnd = () => {
        const current = field.data("DateTimePicker").date()
        let later = relatedDateBefore.val()

        if (later) {
          later = moment(later, $("body").attr("data-dateformat"))
        } else {
          later = dateBefore
        }
        if (dateBefore && later) {
          later = (moment(later, $("body").attr("data-dateformat")).isAfter(moment(dateBefore, $("body").attr("data-dateformat"))) ? dateBefore : later)
        }
        if (
          current !== null &&
          current.isAfter(later) &&
          !current.isSame(later)
        ) {
          field.data("DateTimePicker").date(later.subtract(1, "h"))
        }
        field.data("DateTimePicker").maxDate(later)
      }

      if (relatedDateAfter) {
        relatedDateAfter = $(relatedDateAfter)
        updateStart()
        relatedDateAfter.on("dp.change", updateStart)
      }
      if (relatedDateBefore) {
        relatedDateBefore = $(relatedDateBefore)
        updateEnd()
        relatedDateBefore.on("dp.change", updateEnd)
      }
    }
  )
})
