const reset = function () {
    // Get anchor from URL and open up nested nav
    var anchor = encodeURI(window.location.hash);
    if (anchor) {
        try {
            var link = $('.nav-menu-vertical')
                .find('[href="' + anchor + '"]');
            // If we didn't find a link, it may be because we clicked on
            // something that is not in the sidebar (eg: when using
            // sphinxcontrib.httpdomain it generates headerlinks but those
            // aren't picked up and placed in the toctree). So let's find
            // the closest header in the document and try with that one.
            if (link.length === 0) {
              var doc_link = $('.document a[href="' + anchor + '"]');
              var closest_section = doc_link.closest('div.section');
              // Try again with the closest section entry.
              link = $('.nav-menu-vertical')
                .find('[href="#' + closest_section.attr("id") + '"]');

            }
            $('.nav-menu-vertical li.toctree-l1 li.current')
                .removeClass('current');
            link.closest('li.toctree-l2').addClass('current');
            link.closest('li.toctree-l3').addClass('current');
            link.closest('li.toctree-l4').addClass('current');
        }
        catch (err) {
            console.log("Error expanding nav for anchor", err);
        }
    }
};

reset()
window.addEventListener('hashchange', reset);
