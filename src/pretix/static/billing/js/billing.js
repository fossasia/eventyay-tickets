$(document).ready(function () {
    const url = window.location.href;
    const organizerMatch = url.match(/organizer\/([^/]+)/);
    const organizerSlug = organizerMatch ? organizerMatch[1] : null;
    const el = document.getElementById('payment-element');
    const basePath = JSON.parse(document.getElementById('base_path').textContent);
    const changeCardBtn = document.getElementById('change-card-btn');
    const savePaymentInformation = document.getElementById('save-payment-information');
    const paymentInformation = document.getElementById('payment-information');
    let elements;
    let stripe;
    let paymentElement;

   async function initializeStripeAndAPI() {
        paymentInformation.style.display = 'none';
        changeCardBtn.style.display = 'none';

        await fetch(`${basePath}/control/organizer/${organizerSlug}/setup_intent`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        })
            .then(response => {
                if (!response.ok) {
                    if (response.status === 404) {
                        throw new Error('No setup intent found');
                    }
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                stripe = Stripe(data?.stripe_public_key);
                elements = stripe.elements({
                    clientSecret: data?.client_secret,
                });

                if (data?.payment_method_info) {
                    paymentInformation.style.display = 'block';
                    changeCardBtn.style.display = 'block';
                    document.getElementsByClassName('card-number')[0].innerText = `** ** **** ${data?.payment_method_info.card?.last4}`;
                    document.getElementsByClassName('logo')[0].innerText = (data?.payment_method_info.card?.brand).toUpperCase();
                    document.getElementsByClassName('expiration')[0].innerText = `${data?.payment_method_info.card?.exp_month}/${data?.payment_method_info.card?.exp_year}`;
                } else {
                    paymentElement = elements.create('payment', {
                        layout: 'tabs',
                    });
                    paymentElement.mount(el);
                }
            })
            .catch((error) => {
                console.error('Error initializing stripe:', error);
            });
    }

    initializeStripeAndAPI();

    $(changeCardBtn).on('click', function (event) {
        event.preventDefault();

        paymentElement = elements.create('payment', {
            layout: 'tabs',
        });
        paymentElement.mount(el);
    })

    $(savePaymentInformation).on('click', async function (event) {
        event.preventDefault();

        $(savePaymentInformation).prop('disabled', true);
        try {
            const result = await stripe.confirmSetup({
                elements,
                redirect: 'if_required'
            });

            const csrfToken = document.cookie.match(/pretix_csrftoken=([^;]+)/)[1];

            const response = await fetch(`${basePath}/control/organizer/${organizerSlug}/save_payment_information`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({
                    setup_intent_id: result.setupIntent.id,
                }),
            });

            if (response.status === 200) {
                window.location.reload();
            }

        } catch (error) {
            console.error('Error saving payment information:', error);
        } finally {
            $(savePaymentInformation).prop('disabled', false);
        }
    });
});