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
    
    
    $(document).off('click.submenu').on('click.submenu', function (event) {
        if (window.innerWidth <= 768) {
            
            if (!$(event.target).closest('.dashboard-item, #submenu').length) {
                $('.dashboard-item').removeClass('menu-open');
            }
        }
    });
    
    
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
