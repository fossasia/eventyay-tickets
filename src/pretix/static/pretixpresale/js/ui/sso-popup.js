$(function () {
    let ssoPopupWindow = null;
    let ssoPopupCheckInterval = null;

    $("#popupmodal").removeAttr("hidden");

    $("a[data-open-in-popup-window]").on("click", function (event) {
        event.preventDefault();

        $("#popupmodal a").attr("href", this.href);

        let popupUrl = this.href;
        popupUrl += popupUrl.includes("?") ? "&popup_origin=" + window.location.origin : "?popup_origin=" + window.location.origin;
        ssoPopupWindow = window.open(
            popupUrl,
            "presale-popup",
            "scrollbars=yes,resizable=yes,status=yes,location=yes,toolbar=no,menubar=no,width=940,height=620,left=50,top=50"
        );
        $("body").addClass("has-popup");

        ssoPopupCheckInterval = window.setInterval(function () {
            if (ssoPopupWindow.closed) {
                $("body").removeClass("has-popup");
                window.clearInterval(ssoPopupCheckInterval);
            }
        }, 260);
        return false;
    });

    window.addEventListener("message", function (event) {
        if (event.source !== ssoPopupWindow)
            return;
        if (event.data && event.data.__process === "customer_sso_popup") {
            if (event.data.status === "ok") {
                $("#login_sso_data").val(event.data.value);
                $("#login_sso_data").closest("form").submit();
            } else {
                alert(event.data.value);
            }
            event.source.postMessage({'__process': 'popup_close'}, "*");
        }
    }, false);
});