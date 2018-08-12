$(function () {
    "use strict";
    $('[data-toggle="tooltip"]').tooltip()

    $(".datetimepickerfield").each(function () {
        $(this).datetimepicker({
            format: $("body").attr("data-datetimeformat"),
            locale: $("body").attr("data-datetimelocale"),
            useCurrent: false,
            showClear: !$(this).prop("required"),
            icons: {
                time: 'fa fa-clock-o',
                date: 'fa fa-calendar',
                up: 'fa fa-chevron-up',
                down: 'fa fa-chevron-down',
                previous: 'fa fa-chevron-left',
                next: 'fa fa-chevron-right',
                today: 'fa fa-image',
                clear: 'fa fa-trash',
                close: 'fa fa-times'
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
                time: 'fa fa-clock-o',
                date: 'fa fa-calendar',
                up: 'fa fa-chevron-up',
                down: 'fa fa-chevron-down',
                previous: 'fa fa-chevron-left',
                next: 'fa fa-chevron-right',
                today: 'fa fa-image',
                clear: 'fa fa-trash',
                close: 'fa fa-times'
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

    $("input.submission_featured").change(function() {
        var id = this.dataset.id;

        var $status = $(this).parent().siblings('i')
        var $working = $status.filter('.working');
        var $done = $status.filter('.done');
        var $fail = $status.filter('.fail');

        $working.removeClass('d-none');

        var url = 'submissions/' + id + '/toggle_featured';
        let options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('pretalx_csrftoken'),
            },
            credentials: 'include',
        }

        function reset() {
            $status.addClass('d-none');
            setTimeout(function() {
                $status.addClass('d-none');
            }, 3000);
        }

        function fail() {
            this.checked = !this.checked;
            $fail.removeClass('d-none');
        }

        window.fetch(url, options).then((response) => {
            reset();

            if (response.status === 200) {
                $done.removeClass('d-none');
            } else {
                fail();
            }
        }).catch((error) => {
            reset();
            fail();
        })
    });

    $('.checkbox-multi-select input[type=checkbox]').change((ev) => {
        const checkbox = ev.target;
        var multiSelect = checkbox.parentNode;
        while (multiSelect && !multiSelect.classList.contains('checkbox-multi-select')) {
            multiSelect = multiSelect.parentNode;
        }
        if (multiSelect) {
            update_multi_select_caption(multiSelect);
        }
    })
    document.querySelectorAll('.checkbox-multi-select').forEach((element) => {update_multi_select_caption(element)});
});

function update_multi_select_caption(element) {
    var checkboxes = element.querySelectorAll('.checkbox')
    checkboxes = Array.from(checkboxes).filter((element) => {return element.querySelector('input[type=checkbox]').checked});
    const text = checkboxes.map((box) => box.querySelector('label').innerHTML).join(', ')
    const title = element.querySelector('.multi-select-title')
    if (text) {
        title.innerHTML = text;
    } else {
        title.innerHTML = title.dataset.title;
    }
}

function question_page_toggle_view() {
    const variant = $('#id_variant').val()
    var show = variant === "choices" || variant === "multiple_choice";
    $("#answer-options").toggle(show);

    show = variant === "boolean" && $("#id_required").prop("checked");
    $(".alert-required-boolean").toggle(show);

    show = variant === "text" || variant === "string";
    $(".limit-length").toggle(show);
}

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
