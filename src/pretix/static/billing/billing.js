$(document).ready(function () {
    const url = window.location.href;
    const organizerMatch = url.match(/organizer\/([^/]+)/);
    const organizerSlug = organizerMatch ? organizerMatch[1] : null;
    const el = document.getElementById('payment-information');
    const save_btn = document.getElementById('save-payment-information');
    let elements;
    let stripe;
    let paymentElement;

    function initializeStripeAndAPI() {
        if (organizerSlug) {
            fetch(`http://localhost:8000/control/organizer/${organizerSlug}/setup_intent`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
            })
            .then(response => response.json())
            .then(data => {
                console.log('data:', data);
                stripe = Stripe(data?.stripe_public_key);

                elements = stripe.elements({
                    clientSecret: data?.client_secret,
                });

                paymentElement = elements.create('payment', {
                    layout: 'tabs',
                });

                paymentElement.mount(el);
            })
            .catch((error) => {
                console.error('Error:', error);
            });
        } else {
            console.error('Could not extract organizer name from URL');
        }
    }

    initializeStripeAndAPI();

    $(save_btn).on('click', async function (event) {
        event.preventDefault();

        if (!stripe || !elements) {
            console.error('Stripe or elements not initialized');
            return;
        }

        const result = await stripe.confirmSetup({
            elements,
            redirect: 'if_required'
        });

        const csrfToken = document.cookie.match(/pretix_csrftoken=([^;]+)/)[1];
        console.log('CSRF token:', csrfToken);

        if (result.error) {
            const errorMessage = document.createElement('div');
            errorMessage.textContent = result.error.message;
            errorMessage.style.color = 'red';
            document.body.appendChild(errorMessage);
        } else {
            try {
                const response = await fetch(`http://localhost:8000/control/organizer/${organizerSlug}/save_payment_information`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify({
                        setup_intent_id: result.setupIntent.id,
                    }),
                });
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                const data = await response.json();
                console.log('Save successful:', data);
            } catch (error) {
                console.error('Error saving payment information:', error);
            }
        }
    });
});