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

function handleProfileMenuClick() {
    $('.profile-menu').off('click').on('click', function (event) {
        event.preventDefault();
        const link = $(this).find('a');
        if (link.length > 0) {
            window.location.href = link.attr('href');
        }
    });
    $('.submenu-item').off('click').on('click', function (event) {
        event.preventDefault();
        const link = $(this).find('a');
        if (link.length > 0) {
            window.location.href = link.attr('href');
        }
    });
}
