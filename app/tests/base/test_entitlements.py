import pytest
from unittest.mock import MagicMock

from eventyay.base.entitlements import (
    EntitlementDecision,
    check_entitlement,
    get_capability_registry,
    record_usage,
)
from eventyay.base.signals import (
    entitlement_check,
    entitlement_usage_recorded,
    register_entitlements,
)


@pytest.fixture
def dummy_organizer():
    return MagicMock()


@pytest.mark.django_db
def test_check_entitlement_default_allow(dummy_organizer):
    """If no receivers block it, it should return an allowed decision."""
    decision = check_entitlement(dummy_organizer, capability="some_capability")
    assert decision.allowed is True


@pytest.mark.django_db
def test_check_entitlement_denied_bool(dummy_organizer):
    """If a receiver returns False, it should return a denied decision (legacy fallback)."""
    
    def deny_receiver(sender, capability, **kwargs):
        if capability == "restricted_feature":
            return False
        return True

    entitlement_check.connect(deny_receiver)
    try:
        decision_denied = check_entitlement(dummy_organizer, capability="restricted_feature")
        assert decision_denied.allowed is False
        assert decision_denied.reason_code == "denied_by_plugin"
        
        decision_allowed = check_entitlement(dummy_organizer, capability="other_feature")
        assert decision_allowed.allowed is True
    finally:
        entitlement_check.disconnect(deny_receiver)


@pytest.mark.django_db
def test_check_entitlement_denied_decision(dummy_organizer):
    """If a receiver returns a denied EntitlementDecision, it should return that decision."""
    
    def deny_receiver(sender, capability, **kwargs):
        if capability == "restricted_feature":
            return EntitlementDecision(allowed=False, reason_code="limit_reached", limit=10, used=10)
        return EntitlementDecision(allowed=True, limit=10, used=5)

    entitlement_check.connect(deny_receiver)
    try:
        decision_denied = check_entitlement(dummy_organizer, capability="restricted_feature")
        assert decision_denied.allowed is False
        assert decision_denied.reason_code == "limit_reached"
        assert decision_denied.limit == 10
        assert decision_denied.used == 10
        
        decision_allowed = check_entitlement(dummy_organizer, capability="other_feature")
        assert decision_allowed.allowed is True
        assert decision_allowed.limit == 10
        assert decision_allowed.used == 5
    finally:
        entitlement_check.disconnect(deny_receiver)


@pytest.mark.django_db
def test_record_usage(dummy_organizer):
    """Test that record_usage dispatches the correct signal."""
    received = []

    def usage_receiver(sender, capability, amount, **kwargs):
        received.append((sender, capability, amount))

    entitlement_usage_recorded.connect(usage_receiver)
    try:
        record_usage(dummy_organizer, "test_cap", amount=5)
        assert len(received) == 1
        assert received[0] == (dummy_organizer, "test_cap", 5)
    finally:
        entitlement_usage_recorded.disconnect(usage_receiver)


@pytest.mark.django_db
def test_get_capability_registry():
    """Test that get_capability_registry merges dictionaries correctly."""
    
    def reg_receiver_1(sender, **kwargs):
        return {"cap1": "Description 1"}

    def reg_receiver_2(sender, **kwargs):
        return {"cap2": "Description 2"}

    def reg_receiver_invalid(sender, **kwargs):
        return ["invalid list"]

    register_entitlements.connect(reg_receiver_1)
    register_entitlements.connect(reg_receiver_2)
    register_entitlements.connect(reg_receiver_invalid)
    
    try:
        registry = get_capability_registry()
        assert registry == {
            "cap1": "Description 1",
            "cap2": "Description 2",
        }
    finally:
        register_entitlements.disconnect(reg_receiver_1)
        register_entitlements.disconnect(reg_receiver_2)
        register_entitlements.disconnect(reg_receiver_invalid)

@pytest.mark.django_db
def test_check_entitlement_empty_capability(dummy_organizer):
    """Empty capabilities should raise ValueError to prevent fail-open security bypass."""
    with pytest.raises(ValueError, match="Capability cannot be empty"):
        check_entitlement(dummy_organizer, capability="")
