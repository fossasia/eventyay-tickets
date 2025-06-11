$(document).ready(function() {
    // Get the sidebar element
    const sidebar = $('.sidebar');
    const pageWrapper = $('#page-wrapper');
    
    // Create burger menu button with improved styling
    const burgerButton = $('<a class="navbar-toggle" id="sidebar-toggle" style="display: block !important;">' +
                          '<i class="fa fa-bars"></i>' +
                          '</a>');
    
    // Insert burger button into navbar header
    $('.navbar-header').prepend(burgerButton);
    
    // Initialize sidebar state based on screen size
    function initializeSidebar() {
        const width = $(window).width();
        if (width >= 768) {
            // Desktop: start collapsed, remove mobile classes
            sidebar.removeClass('sidebar-visible sidebar-expanded');
            pageWrapper.removeClass('sidebar-expanded');
            $('body').removeClass('sidebar-overlay');
            localStorage.removeItem('sidebarVisible');
        } else {
            // Mobile: restore saved state
            if (localStorage.getItem('sidebarVisible') === '1') {
                sidebar.addClass('sidebar-visible');
                $('body').addClass('sidebar-overlay');
            }
        }
    }
    
    // Initialize on page load
    initializeSidebar();
    
    // Toggle sidebar on burger button click
    burgerButton.on('click', function(e) {
        e.preventDefault();
        const width = $(window).width();
        
        if (width >= 768) {
            // Desktop: toggle expanded state
            sidebar.toggleClass('sidebar-expanded');
            pageWrapper.toggleClass('sidebar-expanded');
            localStorage.setItem('sidebarExpanded', sidebar.hasClass('sidebar-expanded') ? '1' : '');
        } else {
            // Mobile: toggle visibility
            sidebar.toggleClass('sidebar-visible');
            $('body').toggleClass('sidebar-overlay');
            localStorage.setItem('sidebarVisible', sidebar.hasClass('sidebar-visible') ? '1' : '');
        }
    });
    
    // Handle window resize
    $(window).on('resize', function() {
        const width = $(window).width();
        if (width >= 768) {
            // Switching to desktop
            sidebar.removeClass('sidebar-visible');
            $('body').removeClass('sidebar-overlay');
            localStorage.removeItem('sidebarVisible');
            
            // Restore desktop expanded state if saved
            if (localStorage.getItem('sidebarExpanded') === '1') {
                sidebar.addClass('sidebar-expanded');
                pageWrapper.addClass('sidebar-expanded');
            }
        } else {
            // Switching to mobile
            sidebar.removeClass('sidebar-expanded');
            pageWrapper.removeClass('sidebar-expanded');
            localStorage.removeItem('sidebarExpanded');
        }
    });
    
    // Close mobile sidebar when clicking on overlay
    $('body').on('click', function(e) {
        const width = $(window).width();
        if (width < 768 && sidebar.hasClass('sidebar-visible') && 
            !$(e.target).closest('.sidebar').length && 
            !$(e.target).closest('#sidebar-toggle').length) {
            sidebar.removeClass('sidebar-visible');
            $('body').removeClass('sidebar-overlay');
            localStorage.setItem('sidebarVisible', '');
        }
    });
    
    // Auto-expand on hover for desktop (optional - can be removed if you prefer click-only)
    sidebar.on('mouseenter', function() {
        const width = $(window).width();
        if (width >= 768 && !sidebar.hasClass('sidebar-expanded')) {
            sidebar.addClass('sidebar-hover');
        }
    });
    
    sidebar.on('mouseleave', function() {
        sidebar.removeClass('sidebar-hover');
    });
});