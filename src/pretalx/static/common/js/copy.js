$(function () {
    $('[data-toggle="tooltip"]').tooltip()
    $('[data-toggle="tooltip"]').click(function (e) {
        var $temp = $("<input>");
        $("body").append($temp);
        $temp.val(document.location.origin + $(e.currentTarget).data('destination')).select();
        document.execCommand("copy");
        $temp.remove();
    })
});
