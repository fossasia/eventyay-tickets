/*global $, Quill*/
$(function () {
    var page_name = $('#content').data('page-name');

    var slug_generated = !$("form[data-id]").attr("data-id");
    $('#id_slug').on("keydown keyup keypress", function () {
        slug_generated = false;
    });
    $('input[id^=id_title_]').on("keydown keyup keypress change", function () {
        if (slug_generated) {
            var title = $('input[id^=id_title_]').filter(function () {
                return !!this.value;
            }).first().val();  // First non-empty language
            if (typeof title === "undefined") {
                return;
            }
            var slug = title.toLowerCase()
                .replace(/\s+/g, '-')
                .replace(/[^\w\-]+/g, '')
                .replace(/\-\-+/g, '-')
                .replace(/^-+/, '')
                .replace(/-+$/, '')
                .substr(0, 150);
            $('#id_slug').val(slug);
        }
    });

    $('#content ul.nav-tabs a').click(function (e) {
        e.preventDefault();
        $(this).tab('show');
    });


    var quills = {};
    $('.editor').each(function () {
        const a = $(this).html($("textarea[name^=" + page_name + "_content_][lang=" + $(this).attr("data-lng") + "]").val());
        quills[$(this).attr("data-lng")] = new Quill($(this).get(0), {
            theme: 'snow',
            formats: [
                'bold', 'italic', 'link', 'strike', 'code', 'underline', 'script',
                'list', 'align', 'code-block', 'header', 'image'
            ],
            modules: {
                toolbar: [
                    [{'header': [3, 4, 5, false]}],
                    ['bold', 'italic', 'underline', 'strike'],
                    ['link'],
                    ['image'],
                    [{'align': []}],
                    [{'list': 'ordered'}, {'list': 'bullet'}],
                    [{'script': 'sub'}, {'script': 'super'}],
                    ['clean']
                ]
            }
        });
    });

    $('.editor').closest('form').submit(function () {
        $('.editor').each(function () {
            var val = $(this).find('.ql-editor').html();
            $("textarea[name^=" + page_name + "_content_][lang=" + $(this).attr("data-lng") + "]").val(val);
        });
    });
});
