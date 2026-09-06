import logging

from eventyay.base.signals import (
    entitlement_check,
    entitlement_usage_recorded,
    register_entitlements,
)

logger = logging.getLogger(__name__)


def check_entitlement(organizer, capability: str, **kwargs) -> bool:
    """
    Checks if an organizer has a specific capability.
    Dispatches the `entitlement_check` signal.
    If ANY receiver returns False, access is denied.
    Otherwise (if no receivers or all return True/None), access is allowed.
    """
    responses = entitlement_check.send(sender=organizer, capability=capability, **kwargs)
    for receiver, response in responses:
        if response is False:
            return False
    return True


def record_usage(organizer, capability: str, amount: int = 1, **kwargs) -> None:
    """
    Records usage of a capability for an organizer.
    Dispatches the `entitlement_usage_recorded` signal.
    """
    entitlement_usage_recorded.send(
        sender=organizer, capability=capability, amount=amount, **kwargs
    )


def get_capability_registry() -> dict:
    """
    Returns a dictionary of all registered capabilities by dispatching `register_entitlements`.
    """
    registry = {}
    responses = register_entitlements.send(sender=None)
    for receiver, response in responses:
        if isinstance(response, dict):
            registry.update(response)
        elif response is not None:
            logger.warning(
                "Receiver %r for register_entitlements returned %r instead of dict",
                receiver,
                type(response),
            )
    return registry
