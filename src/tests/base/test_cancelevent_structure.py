from datetime import datetime, timedelta
from decimal import Decimal
import json
from unittest.mock import patch

from django.conf import settings
from django.core import mail as djmail
from django.test import TestCase, override_settings
from django.utils.timezone import now
from django_scopes import scope
import pytz

from pretix.base.models import (
    Event, Item, ItemVariation, Order, OrderPosition, Organizer,
    Voucher, WaitingListEntry, SubEvent, Tax, LogEntry,
    GiftCard, Customer, TeamAPIToken
)
from pretix.base.models.orders import (
    OrderFee, OrderPayment, OrderRefund, 
    OrderPaymentProvider, Transaction
)
from pretix.base.payment import PaymentException
from pretix.base.services.cancelevent import (
    cancel_event, EventCancellationException,
    CancellationRule, RefundStrategy
)
from pretix.base.services.invoices import generate_invoice
from pretix.base.services.notifications import notify
from pretix.testutils.scope import classscope
from pretix.base.services.cancelevent import (
    cancel_event, EventCancellationException,
    CancellationRule, RefundStrategy,
    CancellationRuleException
)

class EventCancelBaseTestCase(TestCase):
    """Base class with common setup for cancellation tests"""
    
    def setUp(self):
        # ... base setup code ...

class EventCancelPaymentTests(EventCancelBaseTestCase):
    """Tests focusing on payment and refund handling"""
    
    def test_stripe_refund(self):
        """Test refund via Stripe payment provider"""
    
    def test_paypal_refund(self):
        """Test refund via PayPal"""
    
    def test_mixed_payment_methods(self):
        """Test order paid with multiple payment methods"""
    
    def test_partial_payments(self):
        """Test cancellation with partial payments"""

class EventCancelFeeTests(EventCancelBaseTestCase):
    """Tests for fee calculation and retention"""
    
    def test_percentage_fee(self):
        """Test percentage-based cancellation fee"""
    
    def test_fixed_fee(self):
        """Test fixed cancellation fee"""
    
    def test_per_ticket_fee(self):
        """Test per-ticket cancellation fee"""
    
    def test_tax_handling(self):
        """Test tax calculations on fees"""

class EventCancelNotificationTests(EventCancelBaseTestCase):
    """Tests for notification handling"""
    
    def test_email_templates(self):
        """Test email template rendering"""
    
    def test_notification_queuing(self):
        """Test notification queue system"""
    
    def test_bulk_notifications(self):
        """Test bulk notification handling"""

class EventCancelVoucherTests(EventCancelBaseTestCase):
    """Tests for voucher handling"""
    
    def test_voucher_reactivation(self):
        """Test voucher reactivation"""
    
    def test_special_vouchers(self):
        """Test special voucher types"""

class SubEventCancelTests(EventCancelBaseTestCase):
    """Tests for subevent cancellation"""
    
    def test_series_cancellation(self):
        """Test cancelling event series"""
    
    def test_date_range_cancel(self):
        """Test cancelling date range"""
    
    def test_timezone_handling(self):
        """Test timezone-specific scenarios"""

class EventCancelAPITests(EventCancelBaseTestCase):
    """Tests for API endpoints"""
    
    def test_api_cancel(self):
        """Test API cancellation endpoint"""
    
    def test_api_permissions(self):
        """Test API permission checks"""

class EventCancelInternationalTests(EventCancelBaseTestCase):
    """Tests for international scenarios"""
    
    def test_multi_currency(self):
        """Test multi-currency handling"""
    
    def test_international_formatting(self):
        """Test international format handling"""

class EventCancelEdgeCaseTests(EventCancelBaseTestCase):
    """Tests for edge cases and error conditions"""
    
    def test_network_failure(self):
        """Test network failure handling"""
    
    def test_partial_failure(self):
        """Test partial cancellation failure"""
    
    def test_concurrent_modifications(self):
        """Test concurrent modification handling"""

class EventCancelAuditTests(EventCancelBaseTestCase):
    """Tests for audit logging"""
    
    def test_log_entries(self):
        """Test audit log creation"""
    
    def test_change_tracking(self):
        """Test change tracking"""

class CancellationRuleTests(EventCancelBaseTestCase):
    """Tests for cancellation rules and strategies"""

    def test_percentage_rule(self):
        """Test percentage-based cancellation rule"""
        rule = CancellationRule(
            percentage=Decimal('10.00'),
            fixed_amount=Decimal('0.00'),
            per_ticket_amount=Decimal('0.00')
        )
        
        self._create_paid_order()
        original_amount = self.order.total
        
        calculated_fee = rule.calculate_fee(self.order)
        expected_fee = original_amount * Decimal('0.10')
        
        self.assertEqual(calculated_fee, expected_fee)
        self.assertEqual(rule.get_refund_amount(self.order), original_amount - expected_fee)

    def test_fixed_rule_with_tax(self):
        """Test fixed amount rule with tax considerations"""
        rule = CancellationRule(
            percentage=Decimal('0.00'),
            fixed_amount=Decimal('50.00'),
            per_ticket_amount=Decimal('0.00'),
            include_tax=True
        )
        
        # Create order with specific tax rate
        self.order.fees.create(
            fee_type=OrderFee.FEE_TYPE_TAX,
            value=Decimal('19.00'),
            tax_rate=Decimal('19.00')
        )
        
        calculated_fee = rule.calculate_fee(self.order)
        self.assertEqual(calculated_fee, Decimal('50.00'))
        # Verify tax calculation
        self.assertEqual(
            rule.calculate_tax_amount(calculated_fee),
            Decimal('7.98')  # 19% of 50/(1+19%)
        )

    def test_combined_rule_strategy(self):
        """Test combination of different rule types with refund strategy"""
        rule = CancellationRule(
            percentage=Decimal('5.00'),
            fixed_amount=Decimal('10.00'),
            per_ticket_amount=Decimal('2.00')
        )
        strategy = RefundStrategy(
            rule=rule,
            auto_refund=True,
            refund_as_giftcard=False
        )
        
        self._create_paid_order()
        original_amount = self.order.total
        num_tickets = self.order.positions.count()
        
        # Calculate expected fees
        expected_percentage_fee = original_amount * Decimal('0.05')
        expected_fixed_fee = Decimal('10.00')
        expected_ticket_fee = Decimal('2.00') * num_tickets
        total_expected_fee = expected_percentage_fee + expected_fixed_fee + expected_ticket_fee
        
        calculated_fee = rule.calculate_fee(self.order)
        self.assertEqual(calculated_fee, total_expected_fee)
        
        # Test strategy application
        refund_amount = strategy.calculate_refund_amount(self.order)
        self.assertEqual(refund_amount, original_amount - total_expected_fee)

class EnhancedEdgeCaseTests(EventCancelBaseTestCase):
    """Enhanced tests for edge cases and error conditions"""

    def test_invalid_payment_credentials(self):
        """Test cancellation with invalid payment provider credentials"""
        self._create_paid_order('stripe')
        
        with patch('pretix.base.payment.stripe.Stripe.execute_refund') as mock_refund:
            mock_refund.side_effect = PaymentException("Invalid API key")
            
            with self.assertRaises(EventCancellationException) as ctx:
                cancel_event(
                    self.event.pk,
                    subevent=None,
                    auto_refund=True,
                    keep_fee_fixed="0.00",
                    keep_fee_percentage="0.00",
                    send=False
                )
            
            self.assertIn("Invalid API key", str(ctx.exception))
            self.order.refresh_from_db()
            self.assertNotEqual(self.order.status, Order.STATUS_CANCELED)

    def test_refund_exceeds_limit(self):
        """Test refund amount exceeding provider limits"""
        # Set up order with amount exceeding typical limits
        self.order.total = Decimal('50000.00')  # Assuming 50k is above some provider limits
        self.order.save()
        self._create_paid_order('stripe')
        
        with patch('pretix.base.payment.stripe.Stripe.execute_refund') as mock_refund:
            mock_refund.side_effect = PaymentException("Refund amount exceeds limit")
            
            with self.assertRaises(EventCancellationException):
                cancel_event(
                    self.event.pk,
                    subevent=None,
                    auto_refund=True,
                    keep_fee_fixed="0.00",
                    keep_fee_percentage="0.00",
                    send=False
                )

    @patch('django.db.transaction.atomic')
    def test_database_error_during_refund(self, mock_transaction):
        """Test database errors during refund processing"""
        self._create_paid_order()
        mock_transaction.side_effect = DatabaseError("Lock timeout")
        
        with self.assertRaises(EventCancellationException):
            cancel_event(
                self.event.pk,
                subevent=None,
                auto_refund=True,
                keep_fee_fixed="0.00",
                keep_fee_percentage="0.00",
                send=False
            )

    def test_complex_event_setup(self):
        """Test cancellation with complex event setup"""
        # Create multiple items with variations
        for i in range(3):
            item = Item.objects.create(
                event=self.event,
                name=f'Complex Item {i}',
                default_price=Decimal('50.00'),
                admission=True
            )
            # Add variations
            for j in range(2):
                variation = ItemVariation.objects.create(
                    item=item,
                    value=f'Variation {j}'
                )
                # Create order position with this variation
                OrderPosition.objects.create(
                    order=self.order,
                    item=item,
                    variation=variation,
                    price=Decimal('50.00')
                )
        
        self._create_paid_order()
        
        # Test cancellation with complex setup
        cancel_event(
            self.event.pk,
            subevent=None,
            auto_refund=True,
            keep_fee_fixed="0.00",
            keep_fee_percentage="0.00",
            send=False
        )
        
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CANCELED)
        # Verify all positions are properly canceled
        for position in self.order.positions.all():
            self.assertTrue(position.canceled)

    def test_external_service_failures(self):
        """Test handling of external service failures"""
        self._create_paid_order()
        
        # Test email service failure
        with patch('django.core.mail.EmailMessage.send') as mock_email:
            mock_email.side_effect = Exception("SMTP failure")
            
            # Should complete cancellation despite email failure
            cancel_event(
                self.event.pk,
                subevent=None,
                auto_refund=True,
                keep_fee_fixed="0.00",
                keep_fee_percentage="0.00",
                send=True,
                send_subject="Test",
                send_message="Test"
            )
            
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, Order.STATUS_CANCELED)

    def test_concurrent_modifications(self):
        """Test handling of concurrent modifications"""
        self._create_paid_order()
        
        # Simulate concurrent modification
        with patch('django.db.transaction.atomic') as mock_transaction:
            mock_transaction.side_effect = TransactionManagementError("Concurrent modification")
            
            with self.assertRaises(EventCancellationException):
                cancel_event(
                    self.event.pk,
                    subevent=None,
                    auto_refund=True,
                    keep_fee_fixed="0.00",
                    keep_fee_percentage="0.00",
                    send=False
                )


# more test classes for specific scenarios
