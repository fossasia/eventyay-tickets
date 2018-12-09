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
    if ($('.colorpickerfield').length) {
        $('.colorpickerfield').parent().colorpicker({
            format: 'hex',
            align: 'left',
            autoInputFallback: false,
            customClass: 'colorpicker-2x',
            sliders: {
                 saturation: {
                     maxLeft: 200,
                     maxTop: 200
                 },
                 hue: {
                     maxTop: 200
                 },
                 alpha: {
                    maxTop: 200
                }
            }
        }).on('colorpickerChange', function(e) {

            var rgb = $(this).colorpicker('color')._color.rgb();
            var c = contrast([255,255,255], [rgb.red(), rgb.green(), rgb.blue()]);
            var mark = 'times';
            if ($(this).parent().find(".contrast-state").length === 0) {
                $(this).parent().append("<div class='help-block contrast-state'></div>");
            }
            let goal = null;
            if ($(this).parent().find(".color-visible")) {
                goal = "visible";
            } else {
                goal = "readable";
            }
            var $note = $(this).parent().find(".contrast-state");
            if (goal === "readable") {
                if (c > 7) {
                    $note.html("<span class='fa fa-fw fa-check-circle'></span>")
                        .append('Your color has great contrast and is very easy to read!');
                    $note.addClass("text-success").removeClass("text-warning").removeClass("text-danger");
                } else if (c > 2.5) {
                    $note.html("<span class='fa fa-fw fa-info-circle'></span>")
                        .append('Your color has decent contrast and is probably good-enough to read!');
                    $note.removeClass("text-success").removeClass("text-warning").removeClass("text-danger");
                } else {
                    $note.html("<span class='fa fa-fw fa-warning'></span>")
                        .append('Your color has bad contrast for text on white background, please choose a darker ' +
                            'shade.');
                    $note.addClass("text-danger").removeClass("text-success").removeClass("text-warning");
                }
            } else {
                if (c > 7) {
                    $note.html("<span class='fa fa-fw fa-check-circle'></span>")
                        .append('Your color has great contrast and is very easy to see!');
                    $note.addClass("text-success").removeClass("text-warning").removeClass("text-danger");
                } else if (c > 2.5) {
                    $note.html("<span class='fa fa-fw fa-info-circle'></span>")
                        .append('Your color has decent contrast and is good to see!');
                    $note.removeClass("text-success").removeClass("text-warning").removeClass("text-danger");
                } else {
                    $note.html("<span class='fa fa-fw fa-warning'></span>")
                        .append('Your color has bad contrast and will be hard to spot or differentiate.');
                    $note.addClass("text-danger").removeClass("text-success").removeClass("text-warning");
                }
            }
        })
    }

    document.querySelectorAll('.checkbox-multi-select').forEach((element) => {update_multi_select_caption(element)});
    $('#id_is_reviewer').change((ev) => {
        update_review_override_votes()
    })
    update_review_override_votes()
});

function luminanace(r, g, b) {
    var a = [r, g, b].map(function (v) {
        v /= 255;
        return v <= 0.03928
            ? v / 12.92
            : Math.pow( (v + 0.055) / 1.055, 2.4 );
    });
    return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
}
function contrast(rgb1, rgb2) {
    var l1 = luminanace(rgb1[0], rgb1[1], rgb1[2]) + 0.05,
         l2 = luminanace(rgb2[0], rgb2[1], rgb2[2]) + 0.05,
         ratio = l1/l2
    if (l2 > l1) {ratio = 1/ratio}
    return ratio.toFixed(1)
}

function update_review_override_votes() {
    const review = document.querySelector('#id_is_reviewer')
    if (!review) {return}
    if (review.checked) {
        document.querySelector('label[for=id_review_override_votes]').style.display = ''
        document.querySelector('#id_review_override_votes').style.display = ''
        document.querySelector('#id_review_override_votes + small').style.display = ''
    } else {
        document.querySelector('label[for=id_review_override_votes]').style.display = 'none'
        document.querySelector('#id_review_override_votes').style.display = 'none'
        document.querySelector('#id_review_override_votes + small').style.display = 'none'
    }
}
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
