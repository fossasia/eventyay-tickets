$(function () {
    function updateNowlines() {
        var now = moment();

        $('.nowline').each(function (index, element) {
            var day = $(element).parent();
            var start = moment(day.data('start'));
            var height_seconds = day.data('height');
            var diff_seconds = now.diff(start, 'seconds');
            var diff_px = (diff_seconds / height_seconds) * $(element).siblings(".rooms").height();
            $(element).css('top', diff_px + 'px');
        });
    }

    updateNowlines();
    $('.nowline').css('visibility', 'visible');

    setInterval(updateNowlines, 60);
});
