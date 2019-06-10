$(function () {
    function updateNowlines() {
        var now = moment();

        $('.nowline').each(function (index, element) {
            var day = $(element).parent();
            var start = moment(day.data('start'));
            var diff_seconds = now.diff(start, 'seconds');
            var diff_px = diff_seconds / 60 / 60 * 120;
            $(element).css('top', diff_px + 'px');
        });
    }

    function updateCurrentTalk() {
        var now = moment();

        $('.talk').each(function (index, element) {
            element = $(element);
            var start = moment(element.data('start'));
            var end = moment(element.data('end'));

            if(start < now && end > now) {
                element.addClass('active');
            } else {
                element.removeClass('active');
            }
        });
    }

    updateNowlines();
    $('.nowline').css('visibility', 'visible');

    updateCurrentTalk();

    setInterval(updateNowlines, 60);
    setInterval(updateCurrentTalk, 60);
});
