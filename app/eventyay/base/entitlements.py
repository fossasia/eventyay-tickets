import logging
from dataclasses import dataclass
from typing import Optional

from eventyay.base.signals import (
    entitlement_check,
    entitlement_usage_recorded,
    register_entitlements,
)

logger = logging.getLogger(__name__)


@dataclass
class EntitlementDecision:
    allowed: bool
    limit: Optional[int] = None
    used: Optional[int] = None
    remaining: Optional[int] = None
    reason_code: Optional[str] = None
    message: Optional[str] = None
    upgrade_url: Optional[str] = None


def check_entitlement(
    organizer, capability: str, event=None, quantity: int = 1, **kwargs
) -> EntitlementDecision:
    """
    Checks if an organizer has a specific capability, accommodating a requested quantity.
    Dispatches the `entitlement_check` signal.
    If ANY receiver returns an EntitlementDecision with allowed=False, access is denied.
    Otherwise, returns an EntitlementDecision with allowed=True.
    """
    if not capability:
        raise ValueError("Capability cannot be empty when checking entitlements.")
        
    responses = entitlement_check.send(
        sender=organizer, event=event, capability=capability, quantity=quantity, **kwargs
    )
    
    final_decision = EntitlementDecision(allowed=True)
    
    for receiver, response in responses:
        if isinstance(response, EntitlementDecision):
            if not response.allowed:
                return response
            final_decision = response
        elif response is False:
            return EntitlementDecision(allowed=False, reason_code="denied_by_plugin")
            
    return final_decision


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
