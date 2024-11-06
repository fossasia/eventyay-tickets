import logging
from functools import wraps

import stripe
from django.core.exceptions import ValidationError

from pretix.base.models import Organizer, BillingInvoice
from pretix.base.models.organizer import OrganizerBillingModel
from pretix.base.settings import GlobalSettingsObject

logger = logging.getLogger(__name__)


def get_stripe_key(key_type: str) -> str:
    gs = GlobalSettingsObject()

    try:
        prod_key = getattr(gs.settings, "payment_stripe_connect_{}_key".format(key_type), None)
        test_key = getattr(gs.settings, "payment_stripe_connect_test_{}_key".format(key_type), None)
    except AttributeError as e:
        logger.error("Missing attribute for Stripe %s key: %s", key_type, str(e))
        raise ValidationError(
            "Missing attribute for Stripe {} key: {}. Please contact the administrator to set the Stripe key.".format(
                key_type, str(e)),
        )

    if not prod_key and not test_key:
        logger.error("No Stripe %s key found", key_type)
        raise ValidationError(
            "Please contact the administrator to set the Stripe {} key.".format(key_type)
        )

    logger.info("Get successful %s key", key_type)

    return prod_key or test_key


def get_stripe_secret_key() -> str:
    return get_stripe_key("secret")


def get_stripe_publishable_key() -> str:
    return get_stripe_key("publishable")


def handle_stripe_errors(operation_name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except stripe.error.APIError as e:
                logger.error("Stripe API error during %s: %s", operation_name, str(e))
                raise ValidationError("Stripe service error.")
            except stripe.error.APIConnectionError as e:
                logger.error("API connection error during %s: %s", operation_name, str(e))
                raise ValidationError("Network communication error.")
            except stripe.error.AuthenticationError as e:
                logger.error("Authentication error during %s: %s", operation_name, str(e))
                raise ValidationError("Authentication failed.")
            except stripe.error.CardError as e:
                logger.error("Card error during %s: %s", operation_name, str(e))
                raise ValidationError("Card error.")
            except stripe.error.RateLimitError as e:
                logger.error("Rate limit error during %s: %s", operation_name, str(e))
                raise ValidationError("Too many requests. Please try again later.")
            except stripe.error.InvalidRequestError as e:
                logger.error("Invalid request error during %s: %s", operation_name, str(e))
                raise ValidationError("Invalid request.")
            except stripe.error.SignatureVerificationError as e:
                logger.error("Signature verification failed during %s: %s", operation_name, str(e))
                raise ValidationError("Webhook signature verification failed.")
            except stripe.error.PermissionError as e:
                logger.error("Permission error during %s: %s", operation_name, str(e))
                raise ValidationError("Permission denied.")
            except stripe.error.IdempotencyError as e:
                logger.error("Idempotency error during %s: %s", operation_name, str(e))
                raise ValidationError("Idempotency error.")
            except stripe.error.StripeError as e:
                logger.error("Stripe error during %s: %s", operation_name, str(e))
                raise ValidationError("Payment processing error.")

        return wrapper

    return decorator


@handle_stripe_errors("create_setup_intent")
def create_setup_intent(customer_id: str) -> str:
    stripe.api_key = get_stripe_secret_key()
    stripe_setup_intent = stripe.SetupIntent.create(
        customer=customer_id,
        payment_method_types=["card"],
        usage="off_session",
    )
    logger.info("Created a successful setup intent.")
    billing_settings_updated = OrganizerBillingModel.objects.filter(stripe_customer_id=customer_id).update(
        stripe_setup_intent_id=stripe_setup_intent.id
    )
    if not billing_settings_updated:
        logger.error("No billing settings found for the customer %s", customer_id)
        raise ValidationError("No billing settings found for the customer.")
    return stripe_setup_intent.client_secret


def get_stripe_customer_id(organizer_slug: str) -> str:
    organizer = Organizer.objects.get(slug=organizer_slug)
    if not organizer:
        logger.error("Organizer %s not found.", organizer_slug)
        raise ValidationError("Organizer {} not found.".format(organizer_slug))
    billing_settings = OrganizerBillingModel.objects.filter(
        organizer_id=organizer.id
    ).first()
    if billing_settings and billing_settings.stripe_customer_id:
        return billing_settings.stripe_customer_id
    logger.error(
        "No billing settings or Stripe customer ID found for organizer %s",
        organizer_slug,
    )
    raise ValidationError(
        "No stripe_customer_id found for organizer {}".format(organizer_slug)
    )


@handle_stripe_errors("create_stripe_customer")
def create_stripe_customer(email: str, name: str):
    stripe.api_key = get_stripe_secret_key()
    customer = stripe.Customer.create(
        email=email,
        name=name,
    )
    logger.info("Created a successful customer.")
    return customer


@handle_stripe_errors("update_payment_info")
def update_payment_info(setup_intent_id: str, customer_id: str):
    stripe.api_key = get_stripe_secret_key()
    setup_intent = get_setup_intent(setup_intent_id)
    payment_method = setup_intent.payment_method
    if not payment_method:
        logger.error("No payment method found for the setup intent %s", setup_intent_id)
        raise ValidationError("No payment method found for the setup intent.")
    billing_setting_updated = OrganizerBillingModel.objects.filter(stripe_customer_id=customer_id).update(
        stripe_payment_method_id=payment_method
    )
    if not billing_setting_updated:
        logger.error("No billing settings found for the customer %s", customer_id)
        raise ValidationError("No billing settings found for the customer.")
    attach_payment_method_to_customer(payment_method, customer_id)
    customer_info_updated = stripe.Customer.modify(
        customer_id, invoice_settings={"default_payment_method": payment_method}
    )
    logger.info("Updated successful payment information.")
    return customer_info_updated


@handle_stripe_errors("get_payment_method_info")
def get_payment_method_info(stripe_customer_id: str):
    stripe.api_key = get_stripe_secret_key()
    billing_settings = OrganizerBillingModel.objects.filter(
        stripe_customer_id=stripe_customer_id
    ).first()
    if not billing_settings or not billing_settings.stripe_payment_method_id:
        return None
    payment_method = stripe.PaymentMethod.retrieve(
        billing_settings.stripe_payment_method_id
    )
    logger.info("Retrieve successful payment information.")
    return payment_method


@handle_stripe_errors("update_customer_info")
def update_customer_info(customer_id: str, email: str, name: str):
    stripe.api_key = get_stripe_secret_key()
    updated_customer_info = stripe.Customer.modify(customer_id, email=email, name=name)
    logger.info("Updated successful customer information.")
    return updated_customer_info


@handle_stripe_errors("attach_payment_method_to_customer")
def attach_payment_method_to_customer(payment_method_id: str, customer_id: str):
    stripe.api_key = get_stripe_secret_key()
    attached_payment_method = stripe.PaymentMethod.attach(
        payment_method_id, customer=customer_id
    )
    logger.info(
        "Attached successful payment method.",
    )
    return attached_payment_method


@handle_stripe_errors("get_setup_intent")
def get_setup_intent(setup_intent_id: str):
    stripe.api_key = get_stripe_secret_key()
    setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
    logger.info("Retrieve successful setup intent.")
    return setup_intent


@handle_stripe_errors("create_payment_intent")
def create_payment_intent(amount: int, currency: str, customer_id: str, payment_method_id: str, metadata: dict, invoice_id: str):
    stripe.api_key = get_stripe_secret_key()
    payment_intent = stripe.PaymentIntent.create(
        amount=int(amount*100),
        currency=currency,
        customer=customer_id,
        payment_method=payment_method_id,
        automatic_payment_methods={
            'enabled': True,
            'allow_redirects': 'never'
        },
        metadata=metadata
    )
    billing_invoice_updated = BillingInvoice.objects.filter(id=invoice_id).update(stripe_payment_intent_id=payment_intent.id)
    if not billing_invoice_updated:
        logger.error("No billing invoice found for the invoice %s", invoice_id)
        raise ValidationError("No billing invoice found for the invoice.")
    logger.info("Created a successful payment intent.")
    return payment_intent


@handle_stripe_errors("confirm_payment_intent")
def confirm_payment_intent(payment_intent_id: str, payment_method_id: str):
    stripe.api_key = get_stripe_secret_key()
    payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    payment_intent.confirm(payment_method=payment_method_id)
    logger.info("Confirmed successful payment intent.")
    return payment_intent


def process_auto_billing_charge_stripe(organizer_slug: str, amount: int, currency: str, metadata: dict, invoice_id: str):
    stripe.api_key = get_stripe_secret_key()
    customer_id = get_stripe_customer_id(organizer_slug)
    payment_method = get_payment_method_info(customer_id)
    if not payment_method:
        logger.error("No payment method found for the customer %s", customer_id)
        raise ValidationError("No payment method found for the customer.")
    payment_intent = create_payment_intent(amount, currency, customer_id, payment_method.id, metadata, invoice_id)
    confirm_payment_intent(payment_intent.id, payment_method.id)
    return payment_intent
