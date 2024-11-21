$(function () {
    const basePath = JSON.parse(document.getElementById('base_path').textContent);
    const isAdminMode = JSON.parse(document.getElementById('is_admin_mode').textContent);
    const currentPath = window.location.pathname;
    const queryString = window.location.search;

    const backUrl = `${currentPath}${queryString}`;

    // Constructing logout path using URLSearchParams
    const logoutParams = new URLSearchParams({ back: backUrl });

    const dashboardPath = `/control/`;
    const orderPath = `/control/settings/orders/`;
    const eventPath = `/control/events/`;
    const organizerPath = `/control/organizers/`;

    const accountPath = `/control/settings/`;
    const adminPath = `/control/admin/`;

    const logoutPath = `/control/logout?${logoutParams}`;

    const options = {
        html: true,
        content: `<div data-name="popover-profile-menu">
                    <div class="profile-menu">
                        <a href="${basePath}${dashboardPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-tachometer"></i> ${window.gettext('Dashboard')}
                        </a>
                    </div>
                    <div class="profile-menu">
                        <a href="${basePath}${orderPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-shopping-cart"></i> ${window.gettext('My Orders')}
                        </a>
                    </div>
                    <div class="profile-menu">
                        <a href="${basePath}${eventPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-calendar"></i> ${window.gettext('My Events')}
                        </a>
                    </div>
                     <div class="profile-menu">
                        <a href="${basePath}${organizerPath}" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-users"></i> ${window.gettext('Organizers')}
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
    $('[data-toggle="popover-profile"]').popover(options).click(function(evt) {
        evt.stopPropagation();
        togglePopover(this);

        $('.admin').hide();

        if (isAdminMode) {
            $('.admin').show();
        }

        $(this).on('shown.bs.popover', function () {
           handleProfileMenuClick()
        });
    })
})

$('html').click(function() {
    $('[data-toggle="popover-profile"]').popover('hide');
});
