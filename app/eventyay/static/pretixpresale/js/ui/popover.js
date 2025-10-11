$(function () {
    var organizerName = JSON.parse(document.getElementById('organizer_name').textContent);
    var eventSlug = JSON.parse(document.getElementById('event_slug').textContent);
    var basePath = JSON.parse(document.getElementById('base_path').textContent);
    var options = {
        html: true,
        content: `<div data-name="popover-content">
                            <div class="options">
                                <a href="${basePath}/${organizerName}/${eventSlug}" target="_self" class="btn btn-outline-success">
                                    <i class="fa fa-ticket"></i> ${window.gettext('Tickets')}
                                </a>
                            </div>
                            <div class="options">
                                <a href="${basePath}/control/settings/orders/" target="_self" class="btn btn-outline-success">
                                    <i class="fa fa-shopping-cart"></i> ${window.gettext('My Orders')}
                                </a>
                            </div>
                    </div>`,
        placement: 'bottom',
        trigger: 'manual'

    }
    $('[data-toggle="popover"]').popover(options).click(function(evt) {
        evt.stopPropagation();
        $(this).popover('show');
        $('[data-toggle="popover-profile"]').popover('hide');
    });
})

$(function () {
    var organizerName = JSON.parse(document.getElementById('organizer_name').textContent);
    var eventSlug = JSON.parse(document.getElementById('event_slug').textContent);
    var basePath = JSON.parse(document.getElementById('base_path').textContent);
    var show_organizer_area = JSON.parse(document.getElementById('show_organizer_area').textContent);
    var currentPath = window.location.pathname;
    var queryString = window.location.search;

    var backUrl = `${currentPath}${queryString}`;

    // Constructing logout path using URLSearchParams
    let logoutParams = new URLSearchParams({ back: backUrl });
    var logoutPath = `/common/logout/?${logoutParams}`;

    var profilePath = `/control/settings/`;
    var orderPath = `/control/settings/orders/`;

    var options = {
        html: true,
        content: `<div data-name="popover-profile-menu">
                    <div class="profile-menu">
                        <a href="${basePath}${orderPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-shopping-cart"></i> ${window.gettext('My Orders')}
                        </a>
                    </div>
                    <div class="profile-menu">
                        <a href="${basePath}${profilePath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-user"></i> ${window.gettext('My Account')}
                        </a>
                    </div>
                    <div class="profile-menu organizer-area">
                        <a href="${basePath}/control/event/${organizerName}/${eventSlug}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-users"></i> ${window.gettext('Organizer Area')}
                        </a>
                    </div>
                    <div class="profile-menu">
                        <a href="${basePath}${logoutPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-sign-out"></i> ${window.gettext('Logout')}
                        </a>
                    </div>
                </div>`,
        placement: 'bottom',
        trigger: 'manual'

    }
    $('[data-toggle="popover-profile"]').popover(options).click(function (evt) {
        evt.stopPropagation();
        togglePopover(this);

        // Ensure Organizer Area is hidden initially
        $('.organizer-area').hide();

        // Show Organizer Area if the condition is true
        if (show_organizer_area) {
            $('.organizer-area').show(); // Show the hidden Organizer Area
        }

        $(this).on('shown.bs.popover', function () {
            handleProfileMenuClick();
        });
    })
})

$('html').click(function() {
    $('[data-toggle="popover"]').popover('hide');
    $('[data-toggle="popover-profile"]').popover('hide');
});
