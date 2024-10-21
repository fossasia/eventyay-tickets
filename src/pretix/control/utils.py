from django.shortcuts import redirect
from pretix.base.models import Organizer
from pretix.base.models.organizer import OrganizerBillingModel
from pretix.base.settings import GlobalSettingsObject
from django.contrib import messages
import stripe
import logging

logger = logging.getLogger(__name__)


def get_stripe_secret_key():
    gs = GlobalSettingsObject()
    prod_secret_key = gs.settings.payment_stripe_connect_secret_key
    test_secret_key = gs.settings.payment_stripe_connect_test_secret_key
    if not prod_secret_key and not test_secret_key:
        return messages.error("Please contact the administrator to set the Stripe secret key")
    if prod_secret_key:
        return prod_secret_key
    print('test_secret_key', test_secret_key)
    return test_secret_key

def get_stripe_publishable_key():
    gs = GlobalSettingsObject()
    prod_publishable_key = gs.settings.payment_stripe_connect_publishable_key
    test_publishable_key = gs.settings.payment_stripe_connect_test_publishable_key
    if not prod_publishable_key and not test_publishable_key:
        return messages.error("Please contact the administrator to set the Stripe publishable key")
    if prod_publishable_key:
        return prod_publishable_key
    print('test_publishable_key', test_publishable_key)
    return test_publishable_key


def create_setup_intent(customer_id):
    stripe.api_key = get_stripe_secret_key()

    try:
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card"],
            usage="off_session",
        )
        return setup_intent.client_secret

    except stripe.error.CardError as e:
        logger.error("Card error creating setup intent: %s", str(e))
        return messages.error(f"Card error: {e.user_message}")

    except stripe.error.InvalidRequestError as e:
        logger.error("Invalid request error creating setup intent: %s", str(e))
        return messages.error(f"Invalid request: {e.user_message}")

    except stripe.error.AuthenticationError as e:
        logger.error("Authentication error creating setup intent: %s", str(e))
        return messages.error(f"Authentication error: {e.user_message}")

    except stripe.error.APIConnectionError as e:
        logger.error("API connection error creating setup intent: %s", str(e))
        return messages.error("Network error: {}".format(e))

    except stripe.error.StripeError as e:
        logger.error("Stripe error creating setup intent: %s", str(e))
        return messages.error(f"Stripe error: {e.user_message}")

    except Exception as e:
        logger.error("Unexpected error creating setup intent: %s", str(e))
        return messages.error(f"An unexpected error occurred: {e}")


def get_stripe_customer_id(organizer_slug):
    try:
        organizer = Organizer.objects.get(slug=organizer_slug)
        billing_settings = OrganizerBillingModel.objects.filter(organizer_id=organizer.id).first()

        if billing_settings and billing_settings.stripe_customer_id:
            return billing_settings.stripe_customer_id


    except Organizer.DoesNotExist:
        logger.error("Organizer with slug '%s' does not exist", organizer_slug)
        return messages.error("Organizer does not exist.")

    except Exception as e:
        logger.error("Unexpected error retrieving Stripe customer ID: %s", str(e))
        return messages.error("An unexpected error occurred.")


def create_stripe_customer(email, name):
    stripe.api_key = get_stripe_secret_key()

    try:
        customer = stripe.Customer.create(
            email=email,
            name=name,
        )
        return customer

    except stripe.error.InvalidRequestError as e:
        logger.error("Invalid request error creating customer: %s", str(e))
        return messages.error("Invalid request: {}".format(e.user_message))

    except stripe.error.AuthenticationError as e:
        logger.error("Authentication error: %s", str(e))
        return messages.error("Authentication error: {}".format(e.user_message))

    except stripe.error.CardError as e:
        logger.error("Card error: %s", str(e))
        return messages.error("Card error: {}".format(e.user_message))

    except stripe.error.RateLimitError as e:
        logger.error("Rate limit error: %s", str(e))
        return messages.error("Rate limit error: {}".format(e.user_message))

    except stripe.error.StripeError as e:
        logger.error("Stripe error creating customer: %s", str(e))
        return messages.error("Stripe error: {}".format(e.user_message))

    except Exception as e:
        logger.error("Unexpected error creating Stripe customer: %s", str(e))
        return messages.error("An unexpected error occurred: {}".format(e))


def update_payment_info(setup_intent_id, customer_id):
    stripe.api_key = get_stripe_secret_key()

    try:
        setup_intent = retrieve_setup_intent(setup_intent_id)
        if not setup_intent:
            return messages.error("Failed to retrieve setup intent.")

        payment_method = setup_intent.payment_method
        attach_payment_method_to_customer(payment_method, customer_id)

        updated_customer_info = stripe.Customer.modify(
            customer_id,
            invoice_settings={
                "default_payment_method": payment_method
            }
        )
        return updated_customer_info
    except stripe.error.InvalidRequestError as e:
        logger.error("Invalid request error while updating payment info: %s", str(e))
        return messages.error(f"Invalid request: {e.user_message}")
    except stripe.error.AuthenticationError as e:
        logger.error("Authentication error while updating payment info: %s", str(e))
        return messages.error(f"Authentication error: {e.user_message}")
    except stripe.error.APIConnectionError as e:
        logger.error("API connection error while updating payment info: %s", str(e))
        return messages.error(f"Network error: {str(e)}")
    except stripe.error.StripeError as e:
        logger.error("Stripe error while updating payment info: %s", str(e))
        return messages.error(f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error("Unexpected error while updating payment info: %s", str(e))
        return messages.error(f"An unexpected error occurred: {str(e)}")

def update_customer_info(customer_id, email, name):
    stripe.api_key = get_stripe_secret_key()

    try:
        updated_customer_info = stripe.Customer.modify(
            customer_id,
            email=email,
            name=name
        )
        return updated_customer_info
    except stripe.error.InvalidRequestError as e:
        logger.error("Invalid request error while updating customer info: %s", str(e))
        return messages.error(f"Invalid request: {e.user_message}")
    except stripe.error.AuthenticationError as e:
        logger.error("Authentication error while updating customer info: %s", str(e))
        return messages.error(f"Authentication error: {e.user_message}")
    except stripe.error.APIConnectionError as e:
        logger.error("API connection error while updating customer info: %s", str(e))
        return messages.error(f"Network error: {str(e)}")
    except stripe.error.StripeError as e:
        logger.error("Stripe error while updating customer info: %s", str(e))
        return messages.error(f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error("Unexpected error while updating customer info: %s", str(e))
        return messages.error(f"An unexpected error occurred: {str(e)}")


def attach_payment_method_to_customer(payment_method_id, customer_id):
    stripe.api_key = get_stripe_secret_key()

    try:
        attached_payment_method = stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id
        )
        return attached_payment_method
    except stripe.error.InvalidRequestError as e:
        logger.error("Invalid request error while attaching payment method: %s", str(e))
        return messages.error(f"Invalid request: {e.user_message}")
    except stripe.error.AuthenticationError as e:
        logger.error("Authentication error while attaching payment method: %s", str(e))
        return messages.error(f"Authentication error: {e.user_message}")
    except stripe.error.APIConnectionError as e:
        logger.error("API connection error while attaching payment method: %s", str(e))
        return messages.error(f"Network error: {str(e)}")
    except stripe.error.StripeError as e:
        logger.error("Stripe error while attaching payment method: %s", str(e))
        return messages.error(f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error("Unexpected error while attaching payment method: %s", str(e))
        return messages.error(f"An unexpected error occurred: {str(e)}")


def retrieve_setup_intent(setup_intent_id):
    stripe.api_key = get_stripe_secret_key()

    try:
        setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
        return setup_intent
    except stripe.error.InvalidRequestError as e:
        logger.error("Invalid request error while retrieving setup intent: %s", str(e))
        return messages.error(f"Invalid request: {e.user_message}")
    except stripe.error.AuthenticationError as e:
        logger.error("Authentication error while retrieving setup intent: %s", str(e))
        return messages.error(f"Authentication error: {e.user_message}")
    except stripe.error.APIConnectionError as e:
        logger.error("API connection error while retrieving setup intent: %s", str(e))
        return messages.error(f"Network error: {str(e)}")
    except stripe.error.StripeError as e:
        logger.error("Stripe error while retrieving setup intent: %s", str(e))
        return messages.error(f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error("Unexpected error while retrieving setup intent: %s", str(e))
        return messages.error(f"An unexpected error occurred: {str(e)}")