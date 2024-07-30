$(function () {
    var organizerName = JSON.parse(document.getElementById('organizer_name').textContent);
    var eventSlug = JSON.parse(document.getElementById('event_slug').textContent);
    var options = {
        html: true,
        content: `<div data-name="popover-content">
                            <div class="options">
                                <a href="/${organizerName}/${eventSlug}" target="_self" class="btn btn-outline-success ticket-active">
                                    <i class="fa fa-ticket"></i> ${window.gettext('Tickets')}
                                </a>
                            </div>
                            <div class="options">
                                <a href="/${organizerName}/account" target="_self" class="btn btn-outline-success ticket-active">
                                    <i class="fa fa-shopping-cart"></i> ${window.gettext('My Orders')}
                                </a>
                            </div>
                    </div>`,
        placement: 'bottom'

    }
    $('[data-toggle="popover"]').popover(options)
})