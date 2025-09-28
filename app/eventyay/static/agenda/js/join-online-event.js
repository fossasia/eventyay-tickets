$(function () {
    var popup_window = null;
    var popup_check_interval = null;

    // Unbind any existing click handlers to avoid double binding
    $("#join-event-link").off("click").on("click", function (e) {
        e.preventDefault();  // prevent the default action (redirecting to the href)
        var url = $(this).attr('href');  // get the href attribute

        // Make sure the AJAX request is only triggered once
        $.ajax({
            "method": "GET",
            "url": url,
            "success": function(json) {
                if(json.redirect_url) {
                    window.location.href = json.redirect_url;
                }
            },
            "error": function(jqXHR, textStatus, errorThrown) {
                // handle any errors that occur while making the AJAX request
                $("body").addClass("has-join-popup");

                if(jqXHR.responseText === 'user_not_allowed') {
                    // handle 'user_not_allowed' error
                    $("#join-video-popupmodal").removeAttr("hidden");
                } else if (jqXHR.responseText === 'missing_configuration'){
                    // handle other errors
                    $("#join-video-popupmodal-missing-config").removeAttr("hidden");
                }
            }
        });
    });

    $('#join-online-close-button').click(function() {
        $('#join-video-popupmodal').attr('hidden', 'true');
        $("body").removeClass("has-join-popup");
    });

    $('#join-online-close-button-missing-config').click(function() {
        $('#join-video-popupmodal-missing-config').attr('hidden', 'true');
        $("body").removeClass("has-join-popup");
    });
});
