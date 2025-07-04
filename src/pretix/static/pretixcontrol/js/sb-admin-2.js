/*global $ */
/*
 Based on https://github.com/BlackrockDigital/startbootstrap-sb-admin-2
 Copyright 2013-2016 Blackrock Digital LLC
 MIT License
 Modified by Raphael Michel
 */
//Loads the correct sidebar on window load,
//collapses the sidebar on window resize.
// Sets the min-height of #page-wrapper to window size
$(function () {
    'use strict';

    // Sidebar toggle logic (variables moved up for broader scope if needed, and for clarity)
    const $sidebarToggleButton = $('.navbar-toggle-sidebar'); // Our custom button, now hidden on mobile
    const $defaultBurgerButton = $('.navbar-header > button.navbar-toggle'); // Default Bootstrap/sb-admin-2 button
    const $body = $('body');
    // var $wrapper = $('#wrapper'); // Not directly used in the proposed JS changes

    function isMobileView() {
        return window.innerWidth < 768;
    }

    function applyInitialSidebarState() {
        const minimized = localStorage.getItem('sidebarMinimized');
        if (isMobileView()) {
            // On mobile, 'minimized' means hidden off-canvas. Default to hidden.
            if (minimized === 'false') { // Show only if explicitly set to expanded
                $body.removeClass('sidebar-minimized');
            } else {
                $body.addClass('sidebar-minimized');
                if (minimized !== 'true') { // If null/undefined, set to true for consistency
                    localStorage.setItem('sidebarMinimized', 'true');
                }
            }
        } else { // Desktop view
            // FORCE minimized state on desktop, regardless of localStorage
            $body.addClass('sidebar-minimized');
            localStorage.setItem('sidebarMinimized', 'true');
        }
    }

    // Function to ensure MetisMenu is properly initialized
    function ensureMetisMenuInitialized() {
        // Check if side-menu exists and reinitialize MetisMenu
        if ($('#side-menu').length) {
            $('#side-menu').metisMenu({
                'toggle': false,
            });
            // Make sure active items are properly marked
            $('ul.nav ul.nav-second-level a.active').parent().parent().addClass('in').parent().addClass('active');
        }
    }

    // Apply state immediately on DOM ready
    applyInitialSidebarState();
    
    // Ensure MetisMenu is initialized right away
    ensureMetisMenuInitialized();

    $sidebarToggleButton.on('click', function(e) {
        // Removed isMobileView() check to allow toggle on mobile
        e.preventDefault();
        $body.toggleClass('sidebar-minimized');

        // If we're showing the sidebar (removing minimized class), ensure MetisMenu is initialized
        if (!$body.hasClass('sidebar-minimized') && isMobileView()) {
            ensureMetisMenuInitialized();
        }

        if ($body.hasClass('sidebar-minimized')) {
            localStorage.setItem('sidebarMinimized', 'true');
        } else {
            localStorage.setItem('sidebarMinimized', 'false');
        }
    });

    $defaultBurgerButton.on('click', function(e) {
        if (isMobileView()) {
            // This button now controls our left sidebar on mobile.
            // Prevent its default Bootstrap collapse behavior for '.navbar-nav-collapse'.
            e.preventDefault();
            e.stopPropagation(); // Optional, but good practice to prevent other listeners if any

            $body.toggleClass('sidebar-minimized');

            // If we're showing the sidebar (removing minimized class), ensure MetisMenu is initialized
            if (!$body.hasClass('sidebar-minimized')) {
                ensureMetisMenuInitialized();
            }

            if ($body.hasClass('sidebar-minimized')) {
                localStorage.setItem('sidebarMinimized', 'true');
            } else {
                localStorage.setItem('sidebarMinimized', 'false');
            }
        }
        // If not isMobileView(), this button will perform its default Bootstrap action
        // (if it's even visible on desktop, which it usually isn't if .navbar-collapse is not collapsed).
    });

    $(window).bind("load resize", function () {
        let topOffset = 50;
        const width = (this.window.innerWidth > 0) ? this.window.innerWidth : this.screen.width;
    
        if (width < 768) { // Mobile view
            $('div.navbar-collapse').addClass('collapse'); // Collapse Bootstrap top navbar
            topOffset = 100; // If navbar becomes 2 rows
    
            // On resize TO mobile, consistently hide the sidebar overlay
            // This provides a predictable state when entering mobile view.
            if (!$body.hasClass('sidebar-minimized')) {
                $body.addClass('sidebar-minimized');
                localStorage.setItem('sidebarMinimized', 'true');
            }
        } else { // Desktop view
            $('div.navbar-collapse').removeClass('collapse');
    
            // FORCE minimized state on desktop, regardless of localStorage
            $body.addClass('sidebar-minimized');
            localStorage.setItem('sidebarMinimized', 'true');
        }
        
        // Adjust page wrapper min-height (original sb-admin-2 logic)
        let height = ((this.window.innerHeight > 0) ? this.window.innerHeight : this.screen.height) - 1;
        height = height - topOffset;
        if (height < 1) height = 1;
        if (height > topOffset) {
            $("#page-wrapper").css("min-height", (height) + "px");
        }
    });

    $('ul.nav ul.nav-second-level a.active').parent().parent().addClass('in').parent().addClass('active');
    $('#side-menu').metisMenu({
        'toggle': false,
    });

    // Enhanced click handler for nested submenu behavior
    $('#side-menu').on('click', 'a.has-children', function(e) {
        // Don't prevent default - allow navigation to the URL
        // e.preventDefault(); - Remove this line
        
        // Get the URL from the href attribute
        const url = $(this).attr('href');
        
        // If it's a valid URL (not # or javascript:void(0)), navigate to it
        if (url && url !== '#' && !url.startsWith('javascript:')) {
            window.location.href = url;
            return; // Exit the function to prevent submenu toggling
        }
        
        // The rest of the code will only execute for non-navigational links
        const $this = $(this);
        const $parent = $this.parent('li');
        const $submenu = $parent.find('ul.nav-second-level').first();
        const isMobile = $(window).width() < 768;
        
        if (isMobile) {
            // Mobile behavior: accordion-style (close others at same level)
            const $siblings = $parent.siblings('li').find('ul.nav-second-level');
            $siblings.removeClass('in show mobile-submenu-open').slideUp(200);
            $siblings.parent().removeClass('active');
            
            // Toggle current submenu
            if ($submenu.hasClass('in')) {
                $submenu.removeClass('in show mobile-submenu-open').slideUp(200);
                $parent.removeClass('active');
            } else {
                $submenu.addClass('in show mobile-submenu-open').slideDown(200);
                $parent.addClass('active');
            }
        } else {
            // Desktop behavior: allow multiple submenus open
            if ($submenu.hasClass('in')) {
                $submenu.removeClass('in show').slideUp(200);
                $parent.removeClass('active');
            } else {
                $submenu.addClass('in show').slideDown(200);
                $parent.addClass('active');
            }
        }
    });
    
    // Add hover functionality for desktop
    const setupSidebarHover = function() {
    const $sidebar = $('.sidebar');
    const $body = $('body');
    let hoverTimeout;

    if ($('#sidebar-hover-area').length === 0) {
        $('<div id="sidebar-hover-area"></div>').insertAfter($sidebar);
    }

    const $hoverArea = $('#sidebar-hover-area');

    const updateHoverArea = function() {
        if ($body.hasClass('sidebar-minimized')) {
            const sidebarPos = $sidebar.offset();
            $hoverArea.css({
                position: 'fixed',
                top: sidebarPos ? sidebarPos.top : '0',
                left: '0',
                width: '60px',
                height: '100%',
                zIndex: 999,
                pointerEvents: 'auto',
            }).show();
        } else {
            $hoverArea.hide();
        }
    }

    updateHoverArea();
    $(window).on('resize', updateHoverArea);

    // Clear hover logic
    const expandSidebar = function() {
        clearTimeout(hoverTimeout);
        if ($body.hasClass('sidebar-minimized')) {
            $body.removeClass('sidebar-minimized').addClass('hover-temp-open');
            $hoverArea.hide();
            ensureMetisMenuInitialized();
        }
    }

    const collapseSidebar = function() {
        hoverTimeout = setTimeout(function () {
            $body.addClass('sidebar-minimized').removeClass('hover-temp-open');
            updateHoverArea();
        }, );
    }

    // Expand on hover of sidebar or hover area
    $sidebar.add($hoverArea).on('mouseenter.sidebarHover', expandSidebar);

    // Detect when mouse leaves the entire sidebar region
    $(document).on('mousemove', function (e) {
        if ($body.hasClass('hover-temp-open')) {
            const sidebarRect = $sidebar[0].getBoundingClientRect();
            if (
                e.clientX > sidebarRect.right + 20 ||  // moved too far right
                e.clientY < sidebarRect.top - 20 ||    // moved too far up
                e.clientY > sidebarRect.bottom + 20    // moved too far down
            ) {
                collapseSidebar();
            }
        }
    });
}


    
    // Call setup function on page load
    setupSidebarHover();
    
    // Reapply on window resize
    $(window).on('resize', function() {
        setupSidebarHover();
    });
});
