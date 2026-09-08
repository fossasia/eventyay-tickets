$(function () {
    "use strict";

    var update_currency = function () {
        var currency = $("#id_currency").val() || "";
        $(".currency-addon").text(currency);
        $("#review-currency").text(currency);
        update_step_completion();
    };

    var set_step_completed = function (step_num, is_done) {
        var $item = $('.quickstart-step-item[data-step="' + step_num + '"]');
        if (is_done) {
            $item.addClass("completed");
        } else {
            $item.removeClass("completed");
        }
    };

    var update_step_completion = function () {
        // Step 1: Currency selected
        var currency = ($("#id_currency").val() || "").trim();
        set_step_completed(1, currency !== "");

        // Step 2: At least 1 ticket type with a name
        var named_tickets = 0;
        $("#ticket-type-formset [data-formset-form]").each(function () {
            var $row = $(this);
            var is_deleted = $row.find("input[name$=DELETE]").prop("checked");
            if (is_deleted || $row.css("display") === "none") {
                return;
            }
            var name_val = ($row.find("input[name*='name']").val() || "").trim();
            if (name_val) {
                named_tickets += 1;
            }
        });
        set_step_completed(2, named_tickets > 0);

        // Step 3: Checkout access (completed only when option is selected)
        var step3_selected = $("#id_require_registered_account_for_tickets").is(":checked");
        set_step_completed(3, step3_selected);

        // Step 4: Features (completed only when at least one feature is selected)
        var step4_selected = $("#id_ticket_download").is(":checked") ||
                             $("#id_waiting_list_enabled").is(":checked") ||
                             $("#id_show_quota_left").is(":checked") ||
                             $("#id_attendee_names_required").is(":checked");
        set_step_completed(4, step4_selected);

        // Step 5: Payment
        var paid_tickets = parseInt($("#review-paid-tickets").text(), 10) || 0;
        var selected_methods_count = 0;
        if ($("#id_payment_banktransfer__enabled").is(":checked")) selected_methods_count++;
        if ($("#id_payment_manualpayment__enabled").is(":checked")) selected_methods_count++;
        if ($("#id_payment_stripe__enabled").is(":checked")) selected_methods_count++;
        if ($("#id_payment_paypal__enabled").is(":checked")) selected_methods_count++;

        if (paid_tickets === 0) {
            $("#step-tag-payment").text(gettext("Optional")).removeClass("required").addClass("optional");
            $("#card-payment-tag").text(gettext("Not required (Free tickets)")).removeClass("tag-required").addClass("tag-optional");
            set_step_completed(5, named_tickets > 0 || selected_methods_count > 0);
        } else {
            $("#step-tag-payment").text(gettext("Required")).removeClass("optional").addClass("required");
            $("#card-payment-tag").text(gettext("Required for paid tickets")).removeClass("tag-optional").addClass("tag-required");
            set_step_completed(5, selected_methods_count > 0);
        }

        // Step 6: Review - Complete if all required steps (1, 2, 5) are done
        var step1_done = currency !== "";
        var step2_done = named_tickets > 0;
        var step5_done = (paid_tickets === 0) || (selected_methods_count > 0);
        set_step_completed(6, step1_done && step2_done && step5_done);
    };

    var update_tickets_and_capacity = function () {
        var total_capacity = 0;
        var has_infinite = false;
        var total_tickets = 0;
        var paid_tickets = 0;
        var free_tickets = 0;

        $("#ticket-type-formset [data-formset-form]").each(function () {
            var $row = $(this);
            var is_deleted = $row.find("input[name$=DELETE]").prop("checked");
            if (is_deleted || $row.css("display") === "none") {
                return;
            }

            total_tickets += 1;

            // Price calculation
            var price_str = ($row.find("input[name$=default_price]").val() || "").trim().replace(",", ".");
            var price_num = parseFloat(price_str);
            var is_paid = !isNaN(price_num) && price_num > 0;

            var $statusCell = $row.find(".col-status");
            var $badge = $statusCell.find(".quickstart-status-badge");
            if (!$badge.length) {
                $badge = $("<span></span>").addClass("quickstart-status-badge");
                $statusCell.empty().append($badge);
            }
            if (is_paid) {
                paid_tickets += 1;
                $badge.removeClass("badge-free").addClass("badge-paid").text(gettext("Paid"));
            } else {
                free_tickets += 1;
                $badge.removeClass("badge-paid").addClass("badge-free").text(gettext("Free"));
            }

            // Quota calculation
            var quota_val = ($row.find("input[name$=quota]").val() || "").trim();
            if (quota_val === "") {
                has_infinite = true;
            } else if (!has_infinite) {
                var q = parseInt(quota_val, 10);
                if (!isNaN(q)) {
                    total_capacity += q;
                }
            }
        });

        var override_quota = ($("#id_total_quota").val() || "").trim();
        var cap_text;
        if (override_quota !== "") {
            cap_text = override_quota;
        } else if (total_tickets === 0) {
            cap_text = "0";
        } else {
            cap_text = has_infinite ? "∞" : total_capacity.toString();
        }
        if (override_quota === "" && !$("#id_total_quota").is(":focus")) {
            $("#total-capacity").show();
            $("#id_total_quota").closest("div").addClass("sr-only");
            $("#total-capacity-edit").show();
        }
        $("#total-capacity").text(cap_text);
        $("#review-total-capacity").text(cap_text);
        $("#review-ticket-types").text(total_tickets);
        $("#review-paid-tickets").text(paid_tickets);
        $("#review-free-tickets").text(free_tickets);

        // Toggle payment section visibility based on whether paid tickets exist
        if (paid_tickets > 0) {
            $("#payment-free-state").hide();
            $("#payment-methods-selection").show();
        } else {
            $("#payment-free-state").show();
            $("#payment-methods-selection").hide();
        }

        update_review_summary();
        update_step_completion();
    };

    var update_review_summary = function () {
        // Currency
        var currency = $("#id_currency").val() || "";
        $("#review-currency").text(currency);

        var total_tickets = parseInt($("#review-ticket-types").text(), 10) || 0;
        var paid_tickets = parseInt($("#review-paid-tickets").text(), 10) || 0;

        // Login required
        var login_req = $("#id_require_registered_account_for_tickets").is(":checked");
        $("#review-login-required").text(login_req ? gettext("Yes") : gettext("No"));

        // Waiting list
        var waiting_list = $("#id_waiting_list_enabled").is(":checked");
        $("#review-waiting-list").text(waiting_list ? gettext("Enabled") : gettext("Disabled"));

        // Ticket download
        var ticket_dl = $("#id_ticket_download").is(":checked");
        $("#review-ticket-downloads").text(ticket_dl ? gettext("Enabled") : gettext("Disabled"));

        // Payment methods
        var selected_methods = [];
        if ($("#id_payment_banktransfer__enabled").is(":checked")) {
            selected_methods.push(gettext("Bank transfer"));
        }
        if ($("#id_payment_manualpayment__enabled").is(":checked")) {
            selected_methods.push(gettext("Manual payment"));
        }
        if ($("#id_payment_stripe__enabled").is(":checked")) {
            selected_methods.push(gettext("Stripe"));
        }
        if ($("#id_payment_paypal__enabled").is(":checked")) {
            selected_methods.push(gettext("PayPal"));
        }

        if (selected_methods.length > 0) {
            $("#review-payment-methods").text(selected_methods.join(", "));
        } else {
            $("#review-payment-methods").text(gettext("None selected"));
        }

        // Surface missing required configuration
        var missing_items = [];
        if (total_tickets === 0) {
            missing_items.push({
                text: gettext("At least one ticket type is required to sell tickets."),
                target: "#step-tickets"
            });
            $("#review-ticket-types-missing").show();
        } else {
            $("#review-ticket-types-missing").hide();
        }

        if (paid_tickets > 0 && selected_methods.length === 0) {
            missing_items.push({
                text: gettext("At least one payment method is required for paid tickets."),
                target: "#step-payment"
            });
            $("#review-payment-missing").show();
        } else {
            $("#review-payment-missing").hide();
        }

        if (!currency) {
            missing_items.push({
                text: gettext("Event currency must be selected."),
                target: "#step-currency"
            });
        }

        var $statusBox = $("#review-status-box");
        if (!$statusBox.find(".server-errors").length) {
            var $warning = $("#review-client-warning");
            var $success = $("#review-client-success");
            var $list = $("#review-client-missing-list");

            if (missing_items.length > 0) {
                $list.empty();
                for (var i = 0; i < missing_items.length; i++) {
                    var $li = $("<li></li>");
                    var $a = $("<a></a>").attr("href", missing_items[i].target).text(missing_items[i].text);
                    $li.append($a);
                    $list.append($li);
                }
                $warning.removeClass("is-hidden").show();
                $success.addClass("is-hidden").hide();
            } else {
                $warning.addClass("is-hidden").hide();
                $success.removeClass("is-hidden").show();
            }
        }
    };

    var update_active_step_on_scroll = function () {
        var scroll_pos = $(window).scrollTop() + 160;
        var current_step = 1;
        var steps = [
            { num: 1, id: "#step-currency" },
            { num: 2, id: "#step-tickets" },
            { num: 3, id: "#step-checkout" },
            { num: 4, id: "#step-features" },
            { num: 5, id: "#step-payment" },
            { num: 6, id: "#step-review" }
        ];

        for (var i = 0; i < steps.length; i++) {
            var $el = $(steps[i].id);
            if ($el.length && $el.offset().top <= scroll_pos) {
                current_step = steps[i].num;
            }
        }

        $(".quickstart-step-item").removeClass("active");
        $('.quickstart-step-item[data-step="' + current_step + '"]').addClass("active");
    };

    $(window).on("scroll resize", function () {
        update_active_step_on_scroll();
    });

    // Currency change
    $("#id_currency").on("change", function () {
        update_currency();
    });

    // Inputs change for live calculations
    $("#ticket-type-formset").on("change input keyup", "input", function () {
        update_tickets_and_capacity();
    });

    // Formset row added or deleted
    $("[data-formset]").on("formAdded", function (e, target) {
        var $new_row = $(target);
        if ($new_row.length) {
            $new_row.find("input[name*='name']").each(function () {
                if (!$(this).attr("placeholder") || $(this).attr("placeholder") === "English") {
                    $(this).attr("placeholder", gettext("Ticket name"));
                }
            });
        }
        update_currency();
        update_tickets_and_capacity();
    });

    $("[data-formset]").on("formDeleted", function () {
        update_tickets_and_capacity();
    });

    $("#ticket-type-formset").on("click", "[data-formset-delete-button]", function () {
        var $row = $(this).closest("[data-formset-form]");
        $row.find("input[name$=-DELETE]").prop("checked", true);
        $row.hide();
        update_tickets_and_capacity();
    });

    // Feature and checkout checkboxes change
    $("#id_require_registered_account_for_tickets, #id_waiting_list_enabled, #id_ticket_download, #id_show_quota_left, #id_attendee_names_required").on("change", function () {
        update_review_summary();
        update_step_completion();
    });

    // Payment tile clicks
    $(".payment-tile").on("click", function (e) {
        if ($(e.target).is("input[type=checkbox]")) {
            return;
        }
        var $checkbox = $(this).find("input[type=checkbox]");
        $checkbox.prop("checked", !$checkbox.prop("checked")).trigger("change");
    });

    $(".payment-tile input[type=checkbox]").on("change", function () {
        var $tile = $(this).closest(".payment-tile");
        if ($(this).is(":checked")) {
            $tile.addClass("selected");
        } else {
            $tile.removeClass("selected");
        }

        // Toggle bank transfer details if applicable
        if ($(this).attr("id") === "id_payment_banktransfer__enabled") {
            var $box = $("#banktransfer-details-box");
            if ($(this).is(":checked")) {
                $box.removeClass("is-hidden").slideDown();
            } else {
                $box.slideUp(function () {
                    $(this).addClass("is-hidden");
                });
            }
        }

        update_review_summary();
        update_step_completion();
    });

    // Total capacity override toggle
    $("#total-capacity-edit").on("click", function (e) {
        e.preventDefault();
        var current_cap = $("#total-capacity").text();
        if (current_cap !== "∞" && !$("#id_total_quota").val()) {
            $("#id_total_quota").val(parseInt(current_cap, 10));
        }
        $("#total-capacity").hide();
        $("#id_total_quota").closest("div").removeClass("sr-only");
        $("#id_total_quota").focus();
        $("#total-capacity-edit").hide();
        update_tickets_and_capacity();
    });

    // Total capacity override input listener
    $("#id_total_quota").on("blur", function () {
        if (!($(this).val() || "").trim()) {
            $(this).closest("div").addClass("sr-only");
            $("#total-capacity").show();
            $("#total-capacity-edit").show();
            update_tickets_and_capacity();
        }
    });

    $("#id_total_quota").on("change input keyup", function () {
        var val = ($(this).val() || "").trim();
        if (val === "" && !$(this).is(":focus")) {
            $(this).closest("div").addClass("sr-only");
            $("#total-capacity").show();
            $("#total-capacity-edit").show();
        }
        update_tickets_and_capacity();
    });

    // Stepper navigation & smooth scroll
    $(".quickstart-step-item").on("click", function (e) {
        e.preventDefault();
        var target = $(this).attr("href");
        var $target = $(target);
        if ($target.length) {
            $(".quickstart-step-item").removeClass("active");
            $(this).addClass("active");
            $("html, body").animate({
                scrollTop: $target.offset().top - 80
            }, 300);
        }
    });

    // Smooth scroll for missing configuration links and in-page step links
    $(document).on("click", ".review-missing-list a, .quickstart-wizard-container a[href^='#step-']", function (e) {
        var target = $(this).attr("href");
        var $target = $(target);
        if ($target.length) {
            e.preventDefault();
            $("html, body").animate({
                scrollTop: $target.offset().top - 80
            }, 300);
            $target.addClass("highlight-pulse");
            setTimeout(function () {
                $target.removeClass("highlight-pulse");
            }, 1200);
        }
    });

    // If total capacity is already set, show input field
    if ($("#id_total_quota").val() && $("#id_total_quota").val().trim() !== "") {
        $("#total-capacity").hide();
        $("#id_total_quota").closest("div").removeClass("sr-only");
        $("#total-capacity-edit").hide();
    }

    // Ensure placeholders don't say English
    $("#ticket-type-formset input[name*='name']").each(function () {
        if (!$(this).attr("placeholder") || $(this).attr("placeholder") === "English") {
            $(this).attr("placeholder", gettext("Ticket name"));
        }
    });

    // Initialize state on page load
    update_currency();
    update_tickets_and_capacity();
    update_review_summary();
    update_step_completion();
    update_active_step_on_scroll();
});
