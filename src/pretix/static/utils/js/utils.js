function handleProfileMenuClick() {
    $('.profile-menu').off('click').on('click', function (event) {
        event.preventDefault();
        const link = $(this).find('a');
        if (link.length > 0) {
            window.location.href = link.attr('href');
        }
    });
}
