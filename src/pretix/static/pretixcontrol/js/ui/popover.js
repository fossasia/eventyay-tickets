$(function () {
    var basePath = JSON.parse(document.getElementById('base_path').textContent);
    var currentPath = window.location.pathname;
    var queryString = window.location.search;

    // Using URLSearchParams to handle query parameters
    var searchParams = new URLSearchParams(queryString);
    var backUrl = `${currentPath}${queryString}`;

    // Constructing logout path using URLSearchParams
    var logoutParams = new URLSearchParams();
    logoutParams.set('back', backUrl);
    var logoutPath = `/control/logout?${logoutParams.toString()}`;

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
        $(this).popover('show');
        $('[data-toggle="popover"]').popover('hide');

    })
})

$('html').click(function() {
    $('[data-toggle="popover-profile"]').popover('hide');
});
