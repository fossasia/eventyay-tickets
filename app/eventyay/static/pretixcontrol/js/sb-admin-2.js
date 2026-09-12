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
// mobile-view: collapse on outside click or link click
$(function () {
    'use strict';

    const $body = $('body');
    const $sidebar = $('.sidebar');
    const $navbar = $('.navbar');

    function getNavbarHeight() {
        return $navbar.outerHeight() || 50;
    }
    
    function updateCSSVariables() {
        document.documentElement.style.setProperty('--navbar-height', getNavbarHeight() + 'px');
    }
    const $sidebarToggleButton = $('#sidebar-toggle');
    
    function isMobileView() {
        return window.matchMedia("(max-width: 767px)").matches;
    }


    function isTabletOrDesktop() {
        return window.matchMedia("(min-width: 768px)").matches;
    }

    function toggleSidebar() {
        $body.toggleClass('sidebar-minimized');
        if (isTabletOrDesktop()) {
            localStorage.setItem('sidebar-minimized', $body.hasClass('sidebar-minimized'));
        }
    }

    const SIDEBAR_SCROLL_KEY = 'pretixcontrol_sidebar_scroll';

    function saveSidebarScroll() {
        if ($sidebar.length) {
            try {
                sessionStorage.setItem(SIDEBAR_SCROLL_KEY, $sidebar.scrollTop());
            } catch (e) {}
        }
    }

    function restoreSidebarScroll() {
        if ($sidebar.length) {
            try {
                const savedScroll = sessionStorage.getItem(SIDEBAR_SCROLL_KEY);
                if (savedScroll !== null) {
                    const scrollTop = parseInt(savedScroll, 10);
                    if (!isNaN(scrollTop)) {
                        $sidebar.scrollTop(scrollTop);
                        setTimeout(function () {
                            $sidebar.scrollTop(scrollTop);
                        }, 50);
                    }
                }
            } catch (e) {}
        }
    }

    function initializeSidebar() {
        $('#side-menu').metisMenu({
            toggle: false
        });

        if (isMobileView()) {
            if (!$body.hasClass('sidebar-minimized')) {
                $body.addClass('sidebar-minimized');
            }
        } else {
            if (localStorage.getItem('sidebar-minimized') === null) {
                localStorage.setItem('sidebar-minimized', 'true');
            } else if (localStorage.getItem('sidebar-minimized') === 'true') {
                if (!$body.hasClass('sidebar-minimized')) {
                    $body.addClass('sidebar-minimized');
                }
            } else {
                $body.removeClass('sidebar-minimized');
            }
        }

        $('ul.nav ul.nav-second-level a.active').parent().parent().addClass('in').parent().addClass('active');
        restoreSidebarScroll();
    }

    updateCSSVariables();
    initializeSidebar();

    $sidebarToggleButton.on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        toggleSidebar();
    });

    if ($sidebar.length) {
        let sidebarScrollRaf = null;
        $sidebar.on('scroll', function () {
            if (sidebarScrollRaf !== null) return;
            sidebarScrollRaf = window.requestAnimationFrame(function () {
                sidebarScrollRaf = null;
                saveSidebarScroll();
            });
        });
        $(document).on('click', function (e) {
            if (!isMobileView() || $body.hasClass('sidebar-minimized')) return;
            if ($(e.target).closest('.sidebar, #sidebar-toggle').length) return;
            $body.addClass('sidebar-minimized');
        });
        $sidebar.on('click', 'a[href]', function () {
            saveSidebarScroll();
            if (!isMobileView()) return;
            var href = ($(this).attr('href') || '').trim();
            if (!href || href.charAt(0) === '#') return;
            $body.addClass('sidebar-minimized');
        });
        $(window).on('beforeunload', function () {
            saveSidebarScroll();
        });
    }

    let resizeTimeout;
    $(window).on('resize', function () {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(function() {
            updateCSSVariables();
        }, 150);
    });

    $(window).bind("load resize", function () {
        var topOffset = getNavbarHeight();

        var height = ((this.window.innerHeight > 0) ? this.window.innerHeight : this.screen.height) - 1;
        height = height - topOffset;
        if (height < 1) height = 1;
        if (height > topOffset) {
            $("#page-wrapper").css("min-height", (height) + "px");
        }
    });

    var supportsOverscrollContain = (window.CSS && CSS.supports && CSS.supports('overscroll-behavior: contain'))
        || ('overscrollBehavior' in document.documentElement.style);
    if (!supportsOverscrollContain) {
        function stopPropagationHandler(e) {
            e.stopPropagation();
        }
        $sidebar.on('wheel', stopPropagationHandler);
        $sidebar.on('touchmove', stopPropagationHandler);
    }
});
