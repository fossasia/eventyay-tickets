$(document).ready(function () {
    const url = window.location.href;
    const organizerMatch = url.match(/organizer\/([^/]+)/);
    const organizerSlug = organizerMatch ? organizerMatch[1] : null;
    const el = document.getElementById('payment-element');
    const basePath = JSON.parse(document.getElementById('base_path').textContent);
    const changeCardBtn = document.getElementById('change-card-btn');
    const savePaymentInformationBtn = document.getElementById('save-payment-information');
    const paymentInformation = document.getElementById('payment-information');
    const notification = document.getElementsByClassName('notification')[0];
    const backBtn = document.getElementById('back-btn');
    let elements;
    let stripe;
    let paymentElement;


   async function initializeStripeAndAPI() {
        paymentInformation.style.display = 'none';
        changeCardBtn.style.display = 'none';
        notification.style.display = 'none';
        backBtn.style.display = 'inline-block';
        savePaymentInformationBtn.style.display = 'none';


        if (!organizerSlug) {
            console.error('Organizer slug not found');
            return;
        }

        await fetch(`${basePath}/control/organizer/${organizerSlug}/setup_intent`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        if (response.status === 400) {
                            savePaymentInformationBtn.style.display = 'none';
                            backBtn.style.display = 'inline-block';
                            throw new Error(JSON.stringify(errorData));
                        }
                    });
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
                    savePaymentInformationBtn.style.display = 'inline-block';
                    backBtn.style.display = 'none';
                }
            })
            .catch((error) => {
                const parsedError = JSON.parse(error.message);
                const errorArray = JSON.parse(parsedError.error.replace(/'/g, '"'));
                const errorMessage = errorArray[0];
                notification.style.display = 'block';
                notification.innerText = errorMessage;
            });
    }


    initializeStripeAndAPI();


    $(changeCardBtn).on('click', function (event) {
        event.preventDefault();

        paymentElement = elements.create('payment', {
            layout: 'tabs',
        });
        paymentElement.mount(el);

        $(changeCardBtn).prop('disabled', true);
        backBtn.style.display = 'none';
        savePaymentInformationBtn.style.display = 'inline-block';
    })


    document.getElementById("back-btn").addEventListener("click", function () {
        if (!organizerSlug) {
            console.error('Organizer slug not found');
            window.location.href = `${basePath}/control/organizers/`
            return;
        }
        window.location.href = `${basePath}/control/organizer/${organizerSlug}/settings/billing`;
    });


    $(savePaymentInformationBtn).on('click', async function (event) {
        event.preventDefault();

        $(savePaymentInformationBtn).prop('disabled', true);
        try {
            const result = await stripe.confirmSetup({
                elements,
                redirect: 'if_required'
            });

            const csrfToken = document.cookie.match(/pretix_csrftoken=([^;]+)/)[1];

            if (!organizerSlug || !result?.setupIntent?.id || !csrfToken) {
                notification.style.display = 'block';
                notification.innerText = 'An error occurred while saving payment information. Please try again.';
                savePaymentInformationBtn.style.display = 'inline-block';
                backBtn.style.display = 'none';
                return;
            }

            if (result) {
                await fetch(`${basePath}/control/organizer/${organizerSlug}/save_payment_information`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({
                    setup_intent_id: result?.setupIntent?.id,
                }),
            }).then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        if (response.status === 400) {
                            savePaymentInformationBtn.style.display = 'none';
                            backBtn.style.display = 'inline-block';
                            throw new Error(JSON.stringify(errorData));
                        }
                    });
                }
                return response.json();
            }).then(data => {
                notification.style.display = 'block';
                notification.innerText = 'Payment information saved successfully.';
                notification.style.color = 'green';
                window.location.reload()
            })
            .catch((error) => {
                const parsedError = JSON.parse(error.message);
                const errorArray = JSON.parse(parsedError.error.replace(/'/g, '"'));
                const errorMessage = errorArray[0];
                notification.style.display = 'block';
                notification.innerText = errorMessage;
            });
            }
        } catch (error) {
            console.error('Error saving payment information:', error);
        } finally {
            $(savePaymentInformationBtn).prop('disabled', false);
        }
    });
});
