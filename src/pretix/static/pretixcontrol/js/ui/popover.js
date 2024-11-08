$(function () {
    var basePath = JSON.parse(document.getElementById('base_path').textContent);
    let is_admin_mode = JSON.parse(document.getElementById('is_admin_mode').textContent);
    var currentPath = window.location.pathname;
    var queryString = window.location.search;

    var backUrl = `${currentPath}${queryString}`;

    // Constructing logout path using URLSearchParams
    let logoutParams = new URLSearchParams({ back: backUrl });

    let dashboardPath = `/control/`;
    let eventPath = `/control/events/`;
    let organizerPath = `/control/organizers/`;

    let accountPath = `/control/settings/`;
    let adminPath = `/control/admin/`;

    let logoutPath = `/control/logout?${logoutParams}`;

    var options = {
        html: true,
        content: `<div data-name="popover-profile-menu">
                    <div class="profile-menu">
                        <a href="${basePath}${dashboardPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-tachometer"></i> ${window.gettext('Dashboard')}
                        </a>
                    </div>
                    <div class="profile-menu">
                        <a href="${basePath}${eventPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-calendar"></i> ${window.gettext('My Event')}
                        </a>
                    </div>
                     <div class="profile-menu">
                        <a href="${basePath}${organizerPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-users"></i> ${window.gettext('Organizer')}
                        </a>
                    </div>
                    <div class="profile-menu separator"></div>
                     <div class="profile-menu">
                        <a href="${basePath}${accountPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-user-circle"></i> ${window.gettext('Account')}
                        </a>
                    </div>
                     <div class="profile-menu admin">
                        <a href="${basePath}${adminPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-cog"></i> ${window.gettext('Admin')}
                        </a>
                    </div>
                     <div class="profile-menu separator"></div>
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
        $(this).popover('show');
        $('[data-toggle="popover"]').popover('hide');

        $('.admin').hide();

        if (is_admin_mode) {
            $('.admin').show();
        }

        $(this).on('shown.bs.popover', function () {
            $('.profile-menu').off('click').on('click', function (event) {
                event.preventDefault();
                const link = $(this).find('a');
                if (link.length > 0) {
                    window.location.href = link.attr('href');
                }
            });
        });
    })
})

$('html').click(function() {
    $('[data-toggle="popover-profile"]').popover('hide');
});
