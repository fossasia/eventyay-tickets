$(function () {
    "use strict";

    $(".datetimepickerfield").each(function () {
        $(this).datetimepicker({
            format: $("body").attr("data-datetimeformat"),
            locale: $("body").attr("data-datetimelocale"),
            useCurrent: false,
            showClear: !$(this).prop("required"),
            icons: {
                time: 'far fa-clock',
                date: 'fas fa-calendar',
                up: 'fas fa-chevron-up',
                down: 'fas fa-chevron-down',
                previous: 'fas fa-chevron-left',
                next: 'fas fa-chevron-right',
                today: 'far fa-image',
                clear: 'fas fa-trash',
                close: 'fas fa-times'
            }
        });
    });

    $(".datepickerfield").each(function () {
        var opts = {
            format: $("body").attr("data-dateformat"),
            locale: $("body").attr("data-datetimelocale"),
            useCurrent: false,
            showClear: !$(this).prop("required"),
            icons: {
                time: 'far fa-clock',
                date: 'fas fa-calendar',
                up: 'fas fa-chevron-up',
                down: 'fas fa-chevron-down',
                previous: 'fas fa-chevron-left',
                next: 'fas fa-chevron-right',
                today: 'far fa-image',
                clear: 'fas fa-trash',
                close: 'fas fa-times'
            }
        };
        $(this).datetimepicker(opts);
    });


    $(".datetimepicker[data-date-after], .datepickerfield[data-date-after]").each(function() {
        var later_field = $(this),
            earlier_field = $($(this).attr("data-date-after")),
            update = function () {
                var earlier = earlier_field.data('DateTimePicker').date(),
                    later = later_field.data('DateTimePicker').date();
                if (earlier === null) {
                    earlier = false;
                } else if (later !== null && later.isBefore(earlier) && !later.isSame(earlier)) {
                    later_field.data('DateTimePicker').date(earlier.add(1, 'h'));
                }
                later_field.data('DateTimePicker').minDate(earlier);
            };
        update();
        earlier_field.on("dp.change", update);
    });
    if ($("#answer-options").length) {

        $("#id_variant").change(question_page_toggle_view);
        $("#id_required").change(question_page_toggle_view);
        question_page_toggle_view();
    }
});

function question_page_toggle_view() {
    var show = $("#id_variant").val() == "choices" || $("#id_variant").val() == "multiple_choice";
    $("#answer-options").toggle(show);

    show = $("#id_variant").val() == "boolean" && $("#id_required").prop("checked");
    $(".alert-required-boolean").toggle(show);
}
