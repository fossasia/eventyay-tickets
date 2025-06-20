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
    
    // Desktop click functionality (screen width > 768px)
    $('.dashboard-item').off('click.desktop').on('click.desktop', function (event) {
        if (window.innerWidth > 768) {
            event.preventDefault();
            event.stopPropagation();
            
            // Close other open menus
            $('.dashboard-item').not(this).removeClass('desktop-menu-open desktop-submenu-open');
            
            // Toggle current menu - show both main menu and submenu
            $(this).toggleClass('desktop-menu-open desktop-submenu-open');
        }
    });
    
    // Desktop two-step dismissal logic
    let desktopDismissalStep = 0;
    let desktopDismissalTimer = null;
    
    // Desktop click-outside functionality with two-step dismissal
    $(document).off('click.desktop-submenu').on('click.desktop-submenu', function (event) {
        if (window.innerWidth > 768) {
            const $target = $(event.target);
            const $closestDashboard = $target.closest('.dashboard-item');
            const $closestSubmenu = $target.closest('#submenu');
            const $closestPopover = $target.closest('[data-name="popover-profile-menu"]');
            
            // Don't close if clicking inside submenu or dashboard item
            if ($closestSubmenu.length || $closestDashboard.length) {
                return;
            }
            
            // Handle clicks within the popover area
            if ($closestPopover.length) {
                const hasOpenSubmenu = $('.dashboard-item.desktop-submenu-open').length > 0;
                
                if (hasOpenSubmenu && desktopDismissalStep === 0) {
                    // First click: close submenu only
                    $('.dashboard-item').removeClass('desktop-submenu-open');
                    desktopDismissalStep = 1;
                    
                    // Reset dismissal step after 3 seconds
                    clearTimeout(desktopDismissalTimer);
                    desktopDismissalTimer = setTimeout(() => {
                        desktopDismissalStep = 0;
                    }, 3000);
                    return;
                } else if (desktopDismissalStep === 1) {
                    // Second click: close the entire popover
                    $('.dashboard-item').removeClass('desktop-menu-open');
                    $('[data-toggle="popover-profile"]').popover('hide');
                    desktopDismissalStep = 0;
                    clearTimeout(desktopDismissalTimer);
                    return;
                } else if (!hasOpenSubmenu) {
                    // No submenu open, close popover directly
                    $('.dashboard-item').removeClass('desktop-menu-open');
                    $('[data-toggle="popover-profile"]').popover('hide');
                    desktopDismissalStep = 0;
                    clearTimeout(desktopDismissalTimer);
                    return;
                }
            } else {
                // Click outside popover area - close everything
                $('.dashboard-item').removeClass('desktop-menu-open desktop-submenu-open');
                $('[data-toggle="popover-profile"]').popover('hide');
                desktopDismissalStep = 0;
                clearTimeout(desktopDismissalTimer);
            }
        }
    });
    
    // Desktop escape key support with two-step dismissal
    $(document).off('keydown.desktop-submenu').on('keydown.desktop-submenu', function (event) {
        if (event.key === 'Escape' && window.innerWidth > 768) {
            if ($('.dashboard-item.desktop-submenu-open').length > 0) {
                // Close submenu first
                $('.dashboard-item').removeClass('desktop-submenu-open');
                desktopDismissalStep = 1;
                
                clearTimeout(desktopDismissalTimer);
                desktopDismissalTimer = setTimeout(() => {
                    desktopDismissalStep = 0;
                }, 3000);
            } else {
                // Close main menu and popover
                $('.dashboard-item').removeClass('desktop-menu-open');
                $('[data-toggle="popover-profile"]').popover('hide');
                desktopDismissalStep = 0;
                clearTimeout(desktopDismissalTimer);
            }
        }
    });
    
    // Prevent submenu content clicks from closing the menu (desktop)
    $(document).off('click.desktop-submenu-content').on('click.desktop-submenu-content', '#submenu', function (event) {
        if (window.innerWidth > 768) {
            event.stopPropagation();
        }
    });
    
    // Mobile/tablet functionality (existing code)
    $('.dashboard-item').off('click.dashboard').on('click.dashboard', function (event) {
        if (window.innerWidth <= 768) {
            event.preventDefault();
            event.stopPropagation();
            
            // Close other open menus
            $('.dashboard-item').not(this).removeClass('menu-open');
            
            // Toggle current menu
            $(this).toggleClass('menu-open');
            
            // Add positioning relative to parent for dropdown behavior
            const $this = $(this);
            const $submenu = $this.find('#submenu');
            
            if ($this.hasClass('menu-open')) {
                // Ensure parent has relative positioning
                $this.css('position', 'relative');
                
                // Add show class for animation
                $submenu.addClass('show');
                
                // Check if submenu would go off-screen and adjust if needed
                setTimeout(() => {
                    if ($submenu.length && $submenu[0]) {
                        const submenuRect = $submenu[0].getBoundingClientRect();
                        const viewportWidth = window.innerWidth;
                        const viewportHeight = window.innerHeight;
                        
                        if (submenuRect.right > viewportWidth - 10) {
                            $submenu.css({
                                'left': 'auto',
                                'right': '0'
                            });
                        }
                        
                        if (submenuRect.bottom > viewportHeight - 10) {
                            $submenu.css({
                                'top': 'auto',
                                'bottom': '100%'
                            });
                        }
                    }
                }, 50);
            } else {
                $submenu.removeClass('show');
            }
        }
    });
    
    // Two-step dismissal logic (mobile/tablet only)
    let dismissalStep = 0;
    let dismissalTimer = null;
    
    // Close submenu when clicking outside (mobile/tablet)
    $(document).off('click.submenu').on('click.submenu', function (event) {
        if (window.innerWidth <= 768) {
            const $target = $(event.target);
            const $closestDashboard = $target.closest('.dashboard-item');
            const $closestSubmenu = $target.closest('#submenu');
            const $closestPopover = $target.closest('[data-name="popover-profile-menu"]');
            
            // Don't close if clicking inside submenu or dashboard item
            if ($closestSubmenu.length || $closestDashboard.length) {
                return;
            }
            
            // Handle clicks within the popover area
            if ($closestPopover.length) {
                const hasOpenSubmenu = $('.dashboard-item.menu-open').length > 0;
                
                if (hasOpenSubmenu && dismissalStep === 0) {
                    // First click: close submenu
                    $('.dashboard-item').removeClass('menu-open');
                    $('.dashboard-item #submenu').removeClass('show');
                    dismissalStep = 1;
                    
                    // Reset dismissal step after 3 seconds
                    clearTimeout(dismissalTimer);
                    dismissalTimer = setTimeout(() => {
                        dismissalStep = 0;
                    }, 3000);
                    return;
                } else if (dismissalStep === 1) {
                    // Second click: close the entire popover
                    $('[data-toggle="popover-profile"]').popover('hide');
                    dismissalStep = 0;
                    clearTimeout(dismissalTimer);
                    return;
                } else if (!hasOpenSubmenu) {
                    // No submenu open, close popover directly
                    $('[data-toggle="popover-profile"]').popover('hide');
                    dismissalStep = 0;
                    clearTimeout(dismissalTimer);
                    return;
                }
            } else {
                // Click outside popover area - close everything
                $('.dashboard-item').removeClass('menu-open');
                $('.dashboard-item #submenu').removeClass('show');
                $('[data-toggle="popover-profile"]').popover('hide');
                dismissalStep = 0;
                clearTimeout(dismissalTimer);
            }
        }
    });
    
    // Prevent submenu content clicks from closing the menu (mobile/tablet)
    $(document).off('click.submenu-content').on('click.submenu-content', '#submenu', function (event) {
        if (window.innerWidth <= 768) {
            event.stopPropagation();
        }
    });
    
    // Add escape key support (mobile/tablet)
    $(document).off('keydown.submenu').on('keydown.submenu', function (event) {
        if (event.key === 'Escape' && window.innerWidth <= 768) {
            if ($('.dashboard-item.menu-open').length > 0) {
                // Close submenu first
                $('.dashboard-item').removeClass('menu-open');
                $('.dashboard-item #submenu').removeClass('show');
                dismissalStep = 1;
                
                clearTimeout(dismissalTimer);
                dismissalTimer = setTimeout(() => {
                    dismissalStep = 0;
                }, 3000);
            } else {
                // Close popover
                $('[data-toggle="popover-profile"]').popover('hide');
                dismissalStep = 0;
                clearTimeout(dismissalTimer);
            }
        }
    });
    
   
    $('[data-toggle="popover-profile"]').on('hidden.bs.popover', function () {
        dismissalStep = 0;
        desktopDismissalStep = 0;
        clearTimeout(dismissalTimer);
        clearTimeout(desktopDismissalTimer);
        $('.dashboard-item').removeClass('menu-open desktop-menu-open desktop-submenu-open');
        $('.dashboard-item #submenu').removeClass('show');
    });
}

$(document).ready(function() {
    handleProfileMenuClick();
});