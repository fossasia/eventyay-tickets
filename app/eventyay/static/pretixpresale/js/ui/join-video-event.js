$(function () {
    var popup_window = null
    var popup_check_interval = null

    $("a[join-event-link]").on("click", function (e) {
        e.preventDefault();  // prevent the default action (redirecting to the href)
        var url = $(this).attr('href');  // get the href attribute
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
                if(jqXHR.responseText === 'user_not_allowed') {
                    // handle 'user_not_allowed' error
                    $("body").addClass("has-join-popup")
                    $("#join-video-popupmodal").removeAttr("hidden");
                }
            }
        });
    });
    $('#join-online-close-button').click(function() {
        $('#join-video-popupmodal').attr('hidden', 'true');
        $("body").removeClass("has-join-popup")
    });
})