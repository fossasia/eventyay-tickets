import pytest
from unittest.mock import MagicMock

from eventyay.base.entitlements import (
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
    """If no receivers block it, it should return True."""
    assert check_entitlement(dummy_organizer, "some_capability") is True


@pytest.mark.django_db
def test_check_entitlement_denied(dummy_organizer):
    """If a receiver returns False, it should return False."""
    
    def deny_receiver(sender, capability, **kwargs):
        if capability == "restricted_feature":
            return False
        return True

    entitlement_check.connect(deny_receiver)
    try:
        assert check_entitlement(dummy_organizer, "restricted_feature") is False
        assert check_entitlement(dummy_organizer, "other_feature") is True
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
