/*globals $*/

$(function () {
    var j = 0;
    $(".tabbed-form").each(function () {
        var $form = $(this);
        var $tabs = $("<ul>").addClass("nav nav-tabs").insertBefore($form);
        $form.addClass("tab-content");

        var i = 0;
        var error_preselect = null;
        var hash_preselect = null;
        var validity_error = false;
        $form.children("fieldset").each(function () {
            var $fieldset = $(this);
            var tid = $fieldset.attr("id");
            if (!tid) tid = "tab-" + j + "-" + i;
            var $tabli = $("<li>").appendTo($tabs);
            var $tablink = $("<a>").attr("role", "tab")
                .attr("data-toggle", "tab")
                .attr("href", "#" + tid)
                .text($fieldset.children("legend").text())
                .appendTo($tabli);
            if ($fieldset.find(".has-error, .alert-danger").length > 0) {
                $tablink.append(" ");
                $tablink.append($("<span>").addClass("fa fa-warning text-danger"));
                if (error_preselect === null) {
                    error_preselect = i;
                }
            }
            $fieldset.find("input, select, textarea").on("invalid", function () {
                if ($tablink.find(".fa-warning").length === 0) {
                    $tablink.append(" ");
                    $tablink.append($("<span>").addClass("fa fa-warning text-danger"));
                }
                if (!validity_error) {
                    validity_error = true;
                    $tablink.click();
                }
            });
            $fieldset.children("legend").remove();
            $fieldset.addClass("tab-pane").attr("id", tid);
            var normHash = location.hash ? location.hash.replace(/_/g, "-") : "";
            var normTid = tid ? tid.replace(/_/g, "-") : "";
            if (location.hash && (location.hash === "#" + tid || location.hash === "#" + tid + "-open" || normHash === "#" + normTid || normHash === "#" + normTid + "-open" || $fieldset.find(location.hash).length) && hash_preselect === null) {
                hash_preselect = i;
            }
            i++;
        });
        var preselect = error_preselect !== null ? error_preselect : (hash_preselect !== null ? hash_preselect : 0);
        $tabs.find("a").on('shown.bs.tab', function (e) {
            history.replaceState(null, null, e.target.getAttribute("href"));
            var targetId = e.target.getAttribute("href");
            var $targetPane = $(targetId);
            var $submitGroup = $form.closest("form").find(".submit-group");
            if ($targetPane.is("[data-no-submit]")) {
                $submitGroup.hide();
            } else {
                $submitGroup.show();
            }
        });
        $tabs.find("a").get(preselect).click();
        $(window).on("hashchange", function () {
            if (!location.hash) return;
            var normHash = location.hash.replace(/_/g, "-");
            $tabs.find("a").each(function () {
                var href = $(this).attr("href");
                var normHref = href ? href.replace(/_/g, "-") : "";
                if (location.hash === href || location.hash === href + "-open" || normHash === normHref || normHash === normHref + "-open") {
                    $(this).tab('show');
                }
            });
        });
        $form.closest("form").on("submit", function () {
            validity_error = false;
        });
        j++;
    });
});
