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
    $(window).bind("load resize", function () {
        var topOffset = 50,
            width = (this.window.innerWidth > 0) ? this.window.innerWidth : this.screen.width;
        if (width < 768) {
            $('div.navbar-collapse').addClass('collapse');
            topOffset = 100; // 2-row-menu
        } else {
            $('div.navbar-collapse').removeClass('collapse');
        }

        var height = ((this.window.innerHeight > 0) ? this.window.innerHeight : this.screen.height) - 1;
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
        e.preventDefault();
        
        var $this = $(this);
        var $parent = $this.parent('li');
        var $submenu = $parent.find('ul.nav-second-level').first();
        var isMobile = $(window).width() < 768;
        
        if (isMobile) {
            // Mobile behavior: accordion-style (close others at same level)
            var $siblings = $parent.siblings('li').find('ul.nav-second-level');
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
});
