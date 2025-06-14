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
    

    $('.dashboard-item').off('click.dashboard').on('click.dashboard', function (event) {
        
        if (window.innerWidth <= 768) {
            event.preventDefault();
            event.stopPropagation();
            
           
            $('.dashboard-item').not(this).removeClass('menu-open');
            
            
            $(this).toggleClass('menu-open');
        }
    });
    
    
    // Modified click outside handler for two-step closing
    $(document).off('click.submenu').on('click.submenu', function (event) {
        if (window.innerWidth <= 768) {
            // Check if click is outside both dropdown and submenu
            if (!$(event.target).closest('.dashboard-item, #submenu').length) {
                // Check if submenu is currently open
                if ($('#submenu').is(':visible') || $('.dashboard-item.menu-open #submenu').length > 0) {
                    // First click: close submenu only, keep dropdown open
                    $('#submenu').hide();
                    // Add a flag to indicate submenu was just closed
                    $('.dashboard-item.menu-open').attr('data-submenu-closed', 'true');
                } else if ($('.dashboard-item.menu-open').length > 0) {
                    // Second click: close dropdown menu
                    $('.dashboard-item').removeClass('menu-open').removeAttr('data-submenu-closed');
                }
            } else {
                // Click inside - reset the submenu-closed flag
                $('.dashboard-item.menu-open').removeAttr('data-submenu-closed');
            }
        }
    });
    
    // Remove the duplicate backdrop handler since we're handling it above
    $(document).off('click.backdrop');
    
    $(document).off('click.backdrop').on('click.backdrop', function (event) {
        if (window.innerWidth <= 768) {
            
            if ($(event.target).closest('#submenu').length === 0 && 
                $('.dashboard-item.menu-open').length > 0 && 
                !$(event.target).closest('.dashboard-item').length) {
                $('.dashboard-item').removeClass('menu-open');
            }
        }
    });
    
    
    $(document).off('click.submenu-content').on('click.submenu-content', '#submenu', function (event) {
        event.stopPropagation();
    });
}


$(document).ready(function() {
    handleProfileMenuClick();
});
