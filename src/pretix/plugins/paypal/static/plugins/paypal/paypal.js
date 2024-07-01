'use strict';

var paypalObj = {
    paypal: null,
    client_id: null,
    order_id: null,
    payer_id: null,
    merchant_id: null,
    currency: null,
    method: null,
    additional_disabled_funding: null,
    additional_enabled_funding: null,
    continue_button: null,
    paypage: false,
    method_map: {
        wallet: {
            method: 'wallet',
            funding_source: 'paypal',
            early_auth: true,
        },
        apm: {
            method: 'apm',
            funding_source: null,
            early_auth: false,
        }
    },
    apm_map: {
        paypal: gettext('PayPal'),
        venmo: gettext('Venmo'),
        applepay: gettext('Apple Pay'),
        itau: gettext('Itaú'),
        credit: gettext('PayPal Credit'),
        card: gettext('Credit Card'),
        paylater: gettext('PayPal Pay Later'),
        ideal: gettext('iDEAL'),
        sepa: gettext('SEPA Direct Debit'),
        bancontact: gettext('Bancontact'),
        giropay: gettext('giropay'),
        sofort: gettext('SOFORT'),
        eps: gettext('eps'),
        mybank: gettext('MyBank'),
        p24: gettext('Przelewy24'),
        verkkopankki: gettext('Verkkopankki'),
        payu: gettext('PayU'),
        blik: gettext('BLIK'),
        trustly: gettext('Trustly'),
        zimpler: gettext('Zimpler'),
        maxima: gettext('Maxima'),
        oxxo: gettext('OXXO'),
        boleto: gettext('Boleto'),
        wechatpay: gettext('WeChat Pay'),
        mercadopago: gettext('Mercado Pago')
    },
    readyToSubmitApproval: false,

    load: function () {
        if (paypalObj.paypal === null) {
            paypalObj.client_id = $.trim($("#paypal_client_id").html());
            paypalObj.merchant_id = $.trim($("#paypal_merchant_id").html());
            paypalObj.continue_button = $('.checkout-button-row').closest("form").find(".checkout-button-row .btn-primary");
            paypalObj.continue_button.closest('div').append('<div id="paypal-button-container"></div>');
            paypalObj.additional_disabled_funding = $.trim($("#paypal_disable_funding").html());
            paypalObj.additional_enabled_funding = $.trim($("#paypal_enable_funding").html());
            paypalObj.paypage = Boolean($('#paypal-button-container').data('paypage'));
            paypalObj.order_id = $.trim($("#paypal_oid").html());
            paypalObj.currency = $("body").attr("data-currency");
            paypalObj.locale = this.guessLocale();
        }

        $("input[name=payment][value^='paypal']").change(function () {
            if (paypalObj.paypal !== null) {
                paypalObj.renderButton($(this).val());
            } else {
                paypalObj.continue_button.prop("disabled", true);
            }
        });

        $("input[name=payment]").not("[value^='paypal']").change(function () {
            paypalObj.restore();
        });

        if ($("input[name=payment][value^='paypal']").is(':checked')) {
            paypalObj.continue_button.prop("disabled", true);
        }

        let apmtextselector = $("label[for=input_payment_paypal_apm]");
        apmtextselector.prepend('<span class="fa fa-cog fa-spin"></span> ');

        let sdk_url = 'https://www.paypal.com/sdk/js' +
            '?client-id=' + paypalObj.client_id +
            '&components=buttons,funding-eligibility' +
            '&currency=' + paypalObj.currency;

        if (paypalObj.locale) {
            sdk_url += '&locale=' + paypalObj.locale;
        }

        if (paypalObj.merchant_id) {
            sdk_url += '&merchant-id=' + paypalObj.merchant_id;
        }

        if (paypalObj.additional_disabled_funding) {
            sdk_url += '&disable-funding=' + [paypalObj.additional_disabled_funding].filter(Boolean).join(',');
        }

        if (paypalObj.additional_enabled_funding) {
            sdk_url += '&enable-funding=' + [paypalObj.additional_enabled_funding].filter(Boolean).join(',');
        }

        let ppscript = document.createElement('script');
        let ready = false;
        let head = document.getElementsByTagName("head")[0];
        ppscript.setAttribute('src', sdk_url);
        ppscript.setAttribute('data-csp-nonce', $.trim($("#csp_nonce").html()));
        ppscript.setAttribute('data-page-type', 'checkout');
        ppscript.setAttribute('data-partner-attribution-id', 'eventyay_Cart_PPCP');
        document.head.appendChild(ppscript);

        ppscript.onload = ppscript.onreadystatechange = function () {
            if (!ready && (!this.readyState || this.readyState === "loaded" || this.readyState === "complete")) {
                ready = true;

                paypalObj.paypal = paypal;

                ppscript.onload = ppscript.onreadystatechange = null;
                if (head && ppscript.parentNode) {
                    head.removeChild(ppscript);
                }
            }
        };

        document.addEventListener("visibilitychange", this.onApproveSubmit);
    },

    ready: function () {
        if ($("input[name=payment][value=paypal_apm]").length > 0) {
            paypalObj.renderAPMs();
        }

        if ($("input[name=payment][value^='paypal']").is(':checked')) {
            paypalObj.renderButton($("input[name=payment][value^='paypal']:checked").val());
        } else if ($(".payment-redo-form").length) {
            paypalObj.renderButton($("input[name=payment][value^='paypal']").val());
        } else if ($('#paypal-button-container').data('paypage')) {
            paypalObj.renderButton('paypal_apm');
        }
    },

    restore: function () {
        if (paypalObj.paypal !== null) {
            $('#paypal-button-container').empty()
            paypalObj.continue_button.text(gettext('Continue'));
            paypalObj.continue_button.show();
        }
        paypalObj.continue_button.prop("disabled", false);
    },

    renderButton: function (method) {
        if (method === 'paypal') {
            method = "wallet"
        } else {
            method = method.split('paypal_').at(-1)
        }
        paypalObj.method = paypalObj.method_map[method];

        if (paypalObj.method.method === 'apm' && !paypalObj.paypage) {
            paypalObj.restore();
            return;
        }

        $('#paypal-button-container').empty()
        $('#paypal-card-container').empty()

        let button = paypalObj.paypal.Buttons({
            fundingSource: paypalObj.method.funding_source,
            style: {
                layout: paypalObj.method.early_auth ? 'horizontal' : 'vertical',
                shape: 'rect',
                label: 'pay',
                tagline: false
            },
            createOrder: function (data, actions) {
                if (paypalObj.order_id) {
                    return paypalObj.order_id;
                }

                if (paypalObj.paypage) {
                    return $("#payment_paypal_" + paypalObj.method.method + "_oid");
                } else {
                    var xhrurl = $("#payment_paypal_" + paypalObj.method.method + "_xhr").val();
                }

                return fetch(xhrurl, {
                    method: 'POST'
                }).then(function (res) {
                    return res.json();
                }).then(function (data) {
                    if ('id' in data) {
                        return data.id;
                    } else {
                        location.reload();
                    }
                });
            },
            onApprove: function (data, actions) {
                waitingDialog.show(gettext("Confirming your payment …"));
                paypalObj.order_id = data.orderID;
                paypalObj.payer_id = data.payerID;

                let method = paypalObj.paypage ? "wallet" : paypalObj.method.method;
                let selectorstub = "#payment_paypal_" + method;
                $(selectorstub + "_oid").val(paypalObj.order_id);
                $(selectorstub + "_payer").val(paypalObj.payer_id);

                paypalObj.readyToSubmitApproval = true;
                paypalObj.onApproveSubmit();

            },
        });

        if (button.isEligible()) {
            button.render('#paypal-button-container');
            paypalObj.continue_button.hide();
        } else {
            paypalObj.continue_button.text(gettext('Payment method unavailable'));
            paypalObj.continue_button.show();
        }
    },

    onApproveSubmit: function() {
        if (document.visibilityState === "visible" && paypalObj.readyToSubmitApproval === true) {
            let method = paypalObj.paypage ? "wallet" : paypalObj.method.method;
            let selectorstub = "#payment_paypal_" + method;
            var $form = $(selectorstub + "_oid").closest("form");

            $form.get(0).submit();
        }
    },

    renderAPMs: function () {
        paypalObj.restore();
        let inputselector = $("input[name=payment][value=paypal_apm]");
        let textselector = $("label[for=input_payment_paypal_apm]");
        let textselector2 = inputselector.next("strong");
        let eligibles = [];

        paypalObj.paypal.getFundingSources().forEach(function (fundingSource) {
            if (fundingSource === 'paypal') {
                return;
            }

            let button = paypalObj.paypal.Buttons({
                fundingSource: fundingSource
            });

            if (button.isEligible()) {
                eligibles.push(gettext(paypalObj.apm_map[fundingSource] || fundingSource));
            }
        });

        inputselector.attr('title', eligibles.join(', '));
        textselector.fadeOut(300, function () {
            textselector.text(eligibles.join(', '));
            textselector.fadeIn(300);
        });
        textselector2.fadeOut(300, function () {
            textselector2[0].textContent = eligibles.join(', ');
            textselector2.fadeIn(300);
        });
    },

    guessLocale: function() {
        let allowed_locales = [
            'en_US',
            'ar_DZ',
            'fr_FR',
            'es_ES',
            'zh_CN',
            'de_DE',
            'nl_NL',
            'pt_PT',
            'cs_CZ',
            'da_DK',
            'fi_FI',
            'el_GR',
            'hu_HU',
            'id_ID',
            'he_IL',
            'it_IT',
            'ja_JP',
            'ru_RU',
            'no_NO',
            'pl_PL',
            'sk_SK',
            'sv_SE',
            'th_TH',
            'tr_TR',
        ]
        let lang = $("body").attr("data-locale").split('-')[0];
        return allowed_locales.find(element => element.startsWith(lang));
    }
};

$(function () {
    if (!$("input[name=payment][value^='paypal']").length && !$('#paypal-button-container').data('paypage')) {
        return
    }

    paypalObj.load();

    (async() => {
        while(!paypalObj.paypal)
            await new Promise(resolve => setTimeout(resolve, 1000));
        paypalObj.ready();
    })();
});
