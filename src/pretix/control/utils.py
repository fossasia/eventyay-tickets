import logging
from functools import wraps

import stripe
from django.core.exceptions import ValidationError

from pretix.base.models import Organizer
from pretix.base.models.organizer import OrganizerBillingModel
from pretix.base.settings import GlobalSettingsObject

logger = logging.getLogger(__name__)


def get_stripe_key(key_type: str) -> str:
    gs = GlobalSettingsObject()

    try:
        prod_key = getattr(gs.settings, f"payment_stripeconnect{key_type}_key")
        test_key = getattr(gs.settings, f"payment_stripe_connecttest{key_type}_key")
    except AttributeError as e:
        raise ValidationError(
            f"Missing attribute for Stripe {key_type} key: %s",
            str(e),
            "Please contact the administrator to set the Stripe key.",
        )

    if not prod_key and not test_key:
        raise ValidationError(
            f"Please contact the administrator to set the Stripe {key_type} key."
        )

    return prod_key or test_key


def get_stripe_secret_key() -> str:
    return get_stripe_key("secret")


def get_stripe_publishable_key() -> str:
    return get_stripe_key("publishable")


stripe.api_key = get_stripe_secret_key()


def handle_stripe_errors(operation_name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except stripe.error.APIError as e:
                logger.error(f"Stripe API error during {operation_name}: %s", str(e))
                raise ValidationError(
                    f"Stripe service error: {getattr(e, 'user_message', str(e))}"
                )
            except stripe.error.APIConnectionError as e:
                logger.error(
                    f"API connection error during {operation_name}: %s", str(e)
                )
                raise ValidationError(f"Network communication error: {str(e)}")
            except stripe.error.AuthenticationError as e:
                logger.error(
                    f"Authentication error during {operation_name}: %s", str(e)
                )
                raise ValidationError(
                    f"Authentication failed: {getattr(e, 'user_message', str(e))}"
                )
            except stripe.error.CardError as e:
                logger.error(
                    f"Card error during {operation_name}: %s | Code: %s | Decline code: %s",
                    str(e),
                    e.code,
                    getattr(e, "decline_code", "N/A"),
                )
                raise ValidationError(f"Card error: {e.user_message}")
            except stripe.error.RateLimitError as e:
                logger.error(f"Rate limit error during {operation_name}: %s", str(e))
                raise ValidationError(
                    f"Too many requests. Please try again later: {getattr(e, 'user_message', str(e))}"
                )
            except stripe.error.InvalidRequestError as e:
                logger.error(
                    f"Invalid request error during {operation_name}: %s | Param: %s",
                    str(e),
                    getattr(e, "param", "N/A"),
                )
                raise ValidationError(f"Invalid request: {e.user_message}")
            except stripe.error.SignatureVerificationError as e:
                logger.error(
                    f"Signature verification failed during {operation_name}: %s", str(e)
                )
                raise ValidationError(
                    f"Webhook signature verification failed: {str(e)}"
                )
            except stripe.error.PermissionError as e:
                logger.error(f"Permission error during {operation_name}: %s", str(e))
                raise ValidationError(
                    f"Permission denied: {getattr(e, 'user_message', str(e))}"
                )
            except stripe.error.IdempotencyError as e:
                logger.error(f"Idempotency error during {operation_name}: %s", str(e))
                raise ValidationError(
                    f"Idempotency error: {getattr(e, 'user_message', str(e))}"
                )
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error during {operation_name}: %s", str(e))
                raise ValidationError(
                    f"Payment processing error: {getattr(e, 'user_message', str(e))}"
                )

        return wrapper

    return decorator


@handle_stripe_errors("create_setup_intent")
def create_setup_intent(customer_id: str) -> str:
    stripe_setup_intent = stripe.SetupIntent.create(
        customer=customer_id,
        payment_method_types=["card"],
        usage="off_session",
    )
    OrganizerBillingModel.objects.filter(stripe_customer_id=customer_id).update(
        stripe_setup_intent_id=stripe_setup_intent.id
    )
    return stripe_setup_intent.client_secret


def get_stripe_customer_id(organizer_slug: str) -> str:
    organizer = Organizer.objects.get(slug=organizer_slug)
    billing_settings = OrganizerBillingModel.objects.filter(
        organizer_id=organizer.id
    ).first()

    if billing_settings and billing_settings.stripe_customer_id:
        return billing_settings.stripe_customer_id

    logger.warning(
        "No billing settings or Stripe customer ID found for organizer '%s'",
        organizer_slug,
    )
    raise ValidationError(
        f"No stripe_customer_id found for organizer '{organizer_slug}'"
    )


@handle_stripe_errors("create_stripe_customer")
def create_stripe_customer(email: str, name: str):
    customer = stripe.Customer.create(
        email=email,
        name=name,
    )
    return customer


@handle_stripe_errors("update_payment_info")
def update_payment_info(setup_intent_id: str, customer_id: str):
    setup_intent = get_setup_intent(setup_intent_id)
    payment_method = setup_intent.payment_method
    OrganizerBillingModel.objects.filter(stripe_customer_id=customer_id).update(
        stripe_payment_method_id=payment_method
    )
    attach_payment_method_to_customer(payment_method, customer_id)

    updated_customer_info = stripe.Customer.modify(
        customer_id, invoice_settings={"default_payment_method": payment_method}
    )
    return updated_customer_info


@handle_stripe_errors("get_payment_method_info")
def get_payment_method_info(stripe_customer_id: str):
    billing_settings = OrganizerBillingModel.objects.filter(
        stripe_customer_id=stripe_customer_id
    ).first()
    if billing_settings is None or billing_settings.stripe_payment_method_id is None:
        return None
    payment_method = stripe.PaymentMethod.retrieve(
        billing_settings.stripe_payment_method_id
    )
    return payment_method


@handle_stripe_errors("update_customer_info")
def update_customer_info(customer_id: str, email: str, name: str):
    updated_customer_info = stripe.Customer.modify(customer_id, email=email, name=name)
    return updated_customer_info


@handle_stripe_errors("attach_payment_method_to_customer")
def attach_payment_method_to_customer(payment_method_id: str, customer_id: str):
    attached_payment_method = stripe.PaymentMethod.attach(
        payment_method_id, customer=customer_id
    )
    return attached_payment_method


@handle_stripe_errors("get_setup_intent")
def get_setup_intent(setup_intent_id: str):
    setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
    return setup_intent
