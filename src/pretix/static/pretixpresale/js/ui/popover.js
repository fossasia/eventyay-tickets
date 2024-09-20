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
                                <a href="${basePath}/${organizerName}/account" target="_self" class="btn btn-outline-success">
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
    var basePath = JSON.parse(document.getElementById('base_path').textContent);
    var currentPath = window.location.pathname;
    var queryString = window.location.search;
    var logoutPath = `/${organizerName}/account/logout?next=${encodeURIComponent(currentPath)}%3F${encodeURIComponent(queryString)}`;
    logoutPath = decodeURIComponent(logoutPath);
    var options = {
        html: true,
        content: `<div data-name="popover-profile-menu">
                    <div class="profile-menu">
                        <a href="${basePath}/${organizerName}/account/order" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-shopping-cart"></i> ${window.gettext('My Orders')}
                        </a>
                    </div>
                    <div class="profile-menu">
                        <a href="${basePath}/${organizerName}/account" target="_self" class="btn btn-outline-success">
                            <i class="fa fa-user"></i> ${window.gettext('Account')}
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
    $('[data-toggle="popover"]').popover('hide');
    $('[data-toggle="popover-profile"]').popover('hide');
});
