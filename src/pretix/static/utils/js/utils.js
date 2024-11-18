function togglePopover(element) {
    const popover = $(element).data('bs.popover');
    const isVisible = popover.tip().hasClass('in');
    $('[data-toggle="popover"]').popover('hide');

    if (isVisible) {
        $(element).popover('hide');
    } else {
        $(element).popover('show');
    }
}
