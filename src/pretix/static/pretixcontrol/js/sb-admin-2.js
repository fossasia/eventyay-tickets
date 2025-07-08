$(function () {
    'use strict';

    const $body = $('body');
    const $sidebar = $('.sidebar');
    const $sidebarToggleButton = $('#sidebar-toggle');
    const $navbarCollapseButton = $('.navbar-toggle[data-toggle="collapse"]');

    function isMobileView() {
        return window.matchMedia("(max-width: 767px)").matches;
    }

    function isTabletView() {
        return window.matchMedia("(min-width: 768px) and (max-width: 1024px)").matches;
    }

    function isDesktopView() {
        return window.matchMedia("(min-width: 1025px)").matches;
    }

    function isTabletOrDesktop() {
        return window.matchMedia("(min-width: 768px)").matches;
    }

    function toggleSidebar() {
        if (isMobileView()) {
            // Mobile: Simple toggle without localStorage
            $body.toggleClass('sidebar-minimized');
        } else if (isTabletOrDesktop()) {
            // Desktop/Tablet: Toggle with localStorage persistence
            $body.toggleClass('sidebar-minimized');
            localStorage.setItem('sidebar-minimized', $body.hasClass('sidebar-minimized'));
        }
    }

    function initializeSidebar() {
        $('#side-menu').metisMenu();

        if (isMobileView()) {
            // Mobile: Always start minimized, no localStorage
            $body.addClass('sidebar-minimized');
            // Replace navbar collapse functionality with sidebar toggle
            replaceNavbarCollapseWithSidebarToggle();
        } else {
            // Desktop/Tablet: Start minimized by default, but allow localStorage override
            if (localStorage.getItem('sidebar-minimized') === null) {
                // First time visit - set to minimized by default
                $body.addClass('sidebar-minimized');
                localStorage.setItem('sidebar-minimized', 'true');
            } else if (localStorage.getItem('sidebar-minimized') === 'true') {
                $body.addClass('sidebar-minimized');
            } else {
                $body.removeClass('sidebar-minimized');
            }
            // Replace navbar collapse functionality with sidebar toggle
            replaceNavbarCollapseWithSidebarToggle();
        }
    }

    function replaceNavbarCollapseWithSidebarToggle() {
        // Remove Bootstrap's collapse functionality from the right navbar button
        $navbarCollapseButton.off('click.bs.collapse');
        $navbarCollapseButton.removeAttr('data-toggle');
        $navbarCollapseButton.removeAttr('data-target');
        
        // Add sidebar toggle functionality to the navbar collapse button
        $navbarCollapseButton.on('click.sidebar-toggle', function(e) {
            e.preventDefault();
            e.stopPropagation();
            toggleSidebar();
        });
    }

    initializeSidebar();

    // SIDEBAR TOGGLE: Handle the sidebar burger button specifically (LEFT BUTTON)
    $sidebarToggleButton.on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        toggleSidebar();
    });

    // DESKTOP-ONLY: Hover functionality
    $sidebar.on('mouseenter', function () {
        if (isDesktopView() && $body.hasClass('sidebar-minimized')) {
            $body.addClass('sidebar-hover');
        }
    }).on('mouseleave', function () {
        if (isDesktopView()) {
            $body.removeClass('sidebar-hover');
        }
    });

    // UNIVERSAL: Window resize handler
    let resizeTimeout;
    $(window).on('resize', function () {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(function() {
            // Re-initialize based on current screen size
            if (isMobileView()) {
                // Mobile: Force minimized state and replace navbar collapse
                $body.addClass('sidebar-minimized');
                $body.removeClass('sidebar-hover');
                replaceNavbarCollapseWithSidebarToggle();
            } else {
                // Desktop/Tablet: Restore from localStorage and replace navbar collapse
                if (localStorage.getItem('sidebar-minimized') === 'true') {
                    $body.addClass('sidebar-minimized');
                } else {
                    $body.removeClass('sidebar-minimized');
                }
                replaceNavbarCollapseWithSidebarToggle();
            }
        }, 250);
    });
});
