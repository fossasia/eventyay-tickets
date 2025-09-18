import json
from collections import defaultdict
from decimal import Decimal

import bleach
import dateutil.parser
import pytz
from django.dispatch import receiver
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from i18nfield.strings import LazyI18nString

from eventyay.base.models import (
    Checkin,
    CheckinList,
    Event,
    LogEntry,
    OrderPosition,
    ProductVariation,
    TaxRule,
)
from eventyay.base.signals import logentry_display
from eventyay.base.templatetags.money import money_filter


OVERVIEW_BANLIST = ['eventyay.plugins.sendmail.order.email.sent']


def _display_order_changed(event: Event, logentry: LogEntry):
    data = json.loads(logentry.data)

    text = _('The order has been changed:')
    if logentry.action_type == 'eventyay.event.order.changed.product':
        old_product = str(event.products.get(pk=data['old_product']))
        if data['old_variation']:
            old_product += ' - ' + str(ProductVariation.objects.get(product__event=event, pk=data['old_variation']))
        new_product = str(event.products.get(pk=data['new_product']))
        if data['new_variation']:
            new_product += ' - ' + str(ProductVariation.objects.get(product__event=event, pk=data['new_variation']))
        return (
            text
            + ' '
            + _('Position #{posid}: {old_product} ({old_price}) changed to {new_product} ({new_price}).').format(
                posid=data.get('positionid', '?'),
                old_product=old_product,
                new_product=new_product,
                old_price=money_filter(Decimal(data['old_price']), event.currency),
                new_price=money_filter(Decimal(data['new_price']), event.currency),
            )
        )
    elif logentry.action_type == 'eventyay.event.order.changed.seat':
        return (
            text
            + ' '
            + _('Position #{posid}: Seat "{old_seat}" changed to "{new_seat}".').format(
                posid=data.get('positionid', '?'),
                old_seat=data.get('old_seat'),
                new_seat=data.get('new_seat'),
            )
        )
    elif logentry.action_type == 'eventyay.event.order.changed.subevent':
        old_se = str(event.subevents.get(pk=data['old_subevent']))
        new_se = str(event.subevents.get(pk=data['new_subevent']))
        return (
            text
            + ' '
            + _(
                'Position #{posid}: Event date "{old_event}" ({old_price}) changed to "{new_event}" ({new_price}).'
            ).format(
                posid=data.get('positionid', '?'),
                old_event=old_se,
                new_event=new_se,
                old_price=money_filter(Decimal(data['old_price']), event.currency),
                new_price=money_filter(Decimal(data['new_price']), event.currency),
            )
        )
    elif logentry.action_type == 'eventyay.event.order.changed.price':
        return (
            text
            + ' '
            + _('Price of position #{posid} changed from {old_price} to {new_price}.').format(
                posid=data.get('positionid', '?'),
                old_price=money_filter(Decimal(data['old_price']), event.currency),
                new_price=money_filter(Decimal(data['new_price']), event.currency),
            )
        )
    elif logentry.action_type == 'eventyay.event.order.changed.tax_rule':
        if 'positionid' in data:
            return (
                text
                + ' '
                + _('Tax rule of position #{posid} changed from {old_rule} to {new_rule}.').format(
                    posid=data.get('positionid', '?'),
                    old_rule=TaxRule.objects.get(pk=data['old_taxrule']) if data['old_taxrule'] else '–',
                    new_rule=TaxRule.objects.get(pk=data['new_taxrule']),
                )
            )
        elif 'fee' in data:
            return (
                text
                + ' '
                + _('Tax rule of fee #{fee} changed from {old_rule} to {new_rule}.').format(
                    fee=data.get('fee', '?'),
                    old_rule=TaxRule.objects.get(pk=data['old_taxrule']) if data['old_taxrule'] else '–',
                    new_rule=TaxRule.objects.get(pk=data['new_taxrule']),
                )
            )
    elif logentry.action_type == 'eventyay.event.order.changed.addfee':
        return text + ' ' + str(_('A fee has been added'))
    elif logentry.action_type == 'eventyay.event.order.changed.feevalue':
        return (
            text
            + ' '
            + _('A fee was changed from {old_price} to {new_price}.').format(
                old_price=money_filter(Decimal(data['old_price']), event.currency),
                new_price=money_filter(Decimal(data['new_price']), event.currency),
            )
        )
    elif logentry.action_type == 'eventyay.event.order.changed.cancelfee':
        return (
            text
            + ' '
            + _('A fee of {old_price} was removed.').format(
                old_price=money_filter(Decimal(data['old_price']), event.currency),
            )
        )
    elif logentry.action_type == 'eventyay.event.order.changed.cancel':
        old_product = str(event.products.get(pk=data['old_product']))
        if data['old_variation']:
            old_product += ' - ' + str(ProductVariation.objects.get(pk=data['old_variation']))
        return (
            text
            + ' '
            + _('Position #{posid} ({old_product}, {old_price}) canceled.').format(
                posid=data.get('positionid', '?'),
                old_product=old_product,
                old_price=money_filter(Decimal(data['old_price']), event.currency),
            )
        )
    elif logentry.action_type == 'eventyay.event.order.changed.add':
        product = str(event.products.get(pk=data['product']))
        if data['variation']:
            product += ' - ' + str(ProductVariation.objects.get(product__event=event, pk=data['variation']))
        if data['addon_to']:
            addon_to = OrderPosition.objects.get(order__event=event, pk=data['addon_to'])
            return (
                text
                + ' '
                + _('Position #{posid} created: {product} ({price}) as an add-on to position #{addon_to}.').format(
                    posid=data.get('positionid', '?'),
                    product=product,
                    addon_to=addon_to.positionid,
                    price=money_filter(Decimal(data['price']), event.currency),
                )
            )
        else:
            return (
                text
                + ' '
                + _('Position #{posid} created: {product} ({price}).').format(
                    posid=data.get('positionid', '?'),
                    product=product,
                    price=money_filter(Decimal(data['price']), event.currency),
                )
            )
    elif logentry.action_type == 'eventyay.event.order.changed.secret':
        return (
            text
            + ' '
            + _('A new secret has been generated for position #{posid}.').format(
                posid=data.get('positionid', '?'),
            )
        )
    elif logentry.action_type == 'eventyay.event.order.changed.split':
        old_product = str(event.products.get(pk=data['old_product']))
        if data['old_variation']:
            old_product += ' - ' + str(ProductVariation.objects.get(pk=data['old_variation']))
        url = reverse(
            'control:event.order',
            kwargs={
                'event': event.slug,
                'organizer': event.organizer.slug,
                'code': data['new_order'],
            },
        )
        return mark_safe(
            escape(text)
            + ' '
            + _('Position #{posid} ({old_product}, {old_price}) split into new order: {order}').format(
                old_product=escape(old_product),
                posid=data.get('positionid', '?'),
                order='<a href="{}">{}</a>'.format(url, data['new_order']),
                old_price=money_filter(Decimal(data['old_price']), event.currency),
            )
        )
    elif logentry.action_type == 'eventyay.event.order.changed.split_from':
        return _('This order has been created by splitting the order {order}').format(
            order=data['original_order'],
        )


def _display_checkin(event, logentry):
    data = logentry.parsed_data

    show_dt = False
    if 'datetime' in data:
        dt = dateutil.parser.parse(data.get('datetime'))
        show_dt = abs((logentry.datetime - dt).total_seconds()) > 5 or 'forced' in data
        tz = pytz.timezone(event.settings.timezone)
        dt_formatted = date_format(dt.astimezone(tz), 'SHORT_DATETIME_FORMAT')

    if 'list' in data:
        try:
            checkin_list = event.checkin_lists.get(pk=data.get('list')).name
        except CheckinList.DoesNotExist:
            checkin_list = _('(unknown)')
    else:
        checkin_list = _('(unknown)')

    if logentry.action_type == 'eventyay.event.checkin.unknown':
        if show_dt:
            return _('Unknown scan of code "{barcode}…" at {datetime} for list "{list}", type "{type}".').format(
                posid=data.get('positionid'),
                type=data.get('type'),
                barcode=data.get('barcode')[:16],
                datetime=dt_formatted,
                list=checkin_list,
            )
        else:
            return _('Unknown scan of code "{barcode}…" for list "{list}", type "{type}".').format(
                posid=data.get('positionid'),
                type=data.get('type'),
                barcode=data.get('barcode')[:16],
                list=checkin_list,
            )

    if logentry.action_type == 'eventyay.event.checkin.revoked':
        if show_dt:
            return _(
                'Scan scan of revoked code "{barcode}…" at {datetime} for list "{list}", type "{type}", was uploaded.'
            ).format(
                posid=data.get('positionid'),
                type=data.get('type'),
                barcode=data.get('barcode')[:16],
                datetime=dt_formatted,
                list=checkin_list,
            )
        else:
            return _('Scan of revoked code "{barcode}" for list "{list}", type "{type}", was uploaded.').format(
                posid=data.get('positionid'),
                type=data.get('type'),
                barcode=data.get('barcode')[:16],
                list=checkin_list,
            )

    if logentry.action_type == 'eventyay.event.checkin.denied':
        if show_dt:
            return _(
                'Denied scan of position #{posid} at {datetime} for list "{list}", type "{type}", '
                'error code "{errorcode}".'
            ).format(
                posid=data.get('positionid'),
                type=data.get('type'),
                errorcode=data.get('errorcode'),
                datetime=dt_formatted,
                list=checkin_list,
            )
        else:
            return _(
                'Denied scan of position #{posid} for list "{list}", type "{type}", error code "{errorcode}".'
            ).format(
                posid=data.get('positionid'),
                type=data.get('type'),
                errorcode=data.get('errorcode'),
                list=checkin_list,
            )

    if data.get('type') == Checkin.TYPE_EXIT:
        if show_dt:
            return _('Position #{posid} has been checked out at {datetime} for list "{list}".').format(
                posid=data.get('positionid'), datetime=dt_formatted, list=checkin_list
            )
        else:
            return _('Position #{posid} has been checked out for list "{list}".').format(
                posid=data.get('positionid'), list=checkin_list
            )
    if data.get('first'):
        if show_dt:
            return _('Position #{posid} has been checked in at {datetime} for list "{list}".').format(
                posid=data.get('positionid'), datetime=dt_formatted, list=checkin_list
            )
        else:
            return _('Position #{posid} has been checked in for list "{list}".').format(
                posid=data.get('positionid'), list=checkin_list
            )
    else:
        if data.get('forced'):
            return _(
                'A scan for position #{posid} at {datetime} for list "{list}" has been uploaded even though it has '
                'been scanned already.'.format(
                    posid=data.get('positionid'),
                    datetime=dt_formatted,
                    list=checkin_list,
                )
            )
        return _(
            'Position #{posid} has been scanned and rejected because it has already been scanned before '
            'on list "{list}".'.format(posid=data.get('positionid'), list=checkin_list)
        )


@receiver(signal=logentry_display, dispatch_uid='eventyaycontrol_logentry_display')
def eventyaycontrol_logentry_display(sender: Event, logentry: LogEntry, **kwargs):
    plains = {
        'eventyay.object.cloned': _('This object has been created by cloning.'),
        'eventyay.organizer.changed': _('The organizer has been changed.'),
        'eventyay.organizer.settings': _('The organizer settings have been changed.'),
        'eventyay.giftcards.acceptance.added': _('Gift card acceptance for another organizer has been added.'),
        'eventyay.giftcards.acceptance.removed': _('Gift card acceptance for another organizer has been removed.'),
        'eventyay.webhook.created': _('The webhook has been created.'),
        'eventyay.webhook.changed': _('The webhook has been changed.'),
        'eventyay.event.comment': _("The event's internal comment has been updated."),
        'eventyay.event.canceled': _('The event has been canceled.'),
        'eventyay.event.deleted': _('An event has been deleted.'),
        'eventyay.event.order.modified': _('The order details have been changed.'),
        'eventyay.event.order.unpaid': _('The order has been marked as unpaid.'),
        'eventyay.event.order.secret.changed': _("The order's secret has been changed."),
        'eventyay.event.order.expirychanged': _("The order's expiry date has been changed."),
        'eventyay.event.order.expired': _('The order has been marked as expired.'),
        'eventyay.event.order.paid': _('The order has been marked as paid.'),
        'eventyay.event.order.cancellationrequest.deleted': _('The cancellation request has been deleted.'),
        'eventyay.event.order.refunded': _('The order has been refunded.'),
        'eventyay.event.order.canceled': _('The order has been canceled.'),
        'eventyay.event.order.reactivated': _('The order has been reactivated.'),
        'eventyay.event.order.deleted': _('The test mode order {code} has been deleted.'),
        'eventyay.event.order.placed': _('The order has been created.'),
        'eventyay.event.order.placed.require_approval': _(
            'The order requires approval before it can continue to be processed.'
        ),
        'eventyay.event.order.approved': _('The order has been approved.'),
        'eventyay.event.order.denied': _('The order has been denied.'),
        'eventyay.event.order.contact.changed': _(
            'The email address has been changed from "{old_email}" to "{new_email}".'
        ),
        'eventyay.event.order.contact.confirmed': _(
            'The email address has been confirmed to be working (the user clicked on a link '
            'in the email for the first time).'
        ),
        'eventyay.event.order.phone.changed': _(
            'The phone number has been changed from "{old_phone}" to "{new_phone}".'
        ),
        'eventyay.event.order.locale.changed': _('The order locale has been changed.'),
        'eventyay.event.order.invoice.generated': _('The invoice has been generated.'),
        'eventyay.event.order.invoice.regenerated': _('The invoice has been regenerated.'),
        'eventyay.event.order.invoice.reissued': _('The invoice has been reissued.'),
        'eventyay.event.order.comment': _("The order's internal comment has been updated."),
        'eventyay.event.order.checkin_attention': _(
            "The order's flag to require attention at check-in has been toggled."
        ),
        'eventyay.event.order.payment.changed': _(
            'A new payment {local_id} has been started instead of the previous one.'
        ),
        'eventyay.event.order.email.sent': _('An unidentified type email has been sent.'),
        'eventyay.event.order.email.error': _('Sending of an email has failed.'),
        'eventyay.event.order.email.attachments.skipped': _(
            'The email has been sent without attachments since they would have been too large to be likely to arrive.'
        ),
        'eventyay.event.order.email.custom_sent': _('A custom email has been sent.'),
        'eventyay.event.order.position.email.custom_sent': _('A custom email has been sent to an attendee.'),
        'eventyay.event.order.email.download_reminder_sent': _(
            'An email has been sent with a reminder that the ticket is available for download.'
        ),
        'eventyay.event.order.email.expire_warning_sent': _(
            'An email has been sent with a warning that the order is about to expire.'
        ),
        'eventyay.event.order.email.order_canceled': _(
            'An email has been sent to notify the user that the order has been canceled.'
        ),
        'eventyay.event.order.email.event_canceled': _(
            'An email has been sent to notify the user that the event has been canceled.'
        ),
        'eventyay.event.order.email.order_changed': _(
            'An email has been sent to notify the user that the order has been changed.'
        ),
        'eventyay.event.order.email.order_free': _(
            'An email has been sent to notify the user that the order has been received.'
        ),
        'eventyay.event.order.email.order_paid': _(
            'An email has been sent to notify the user that payment has been received.'
        ),
        'eventyay.event.order.email.order_denied': _(
            'An email has been sent to notify the user that the order has been denied.'
        ),
        'eventyay.event.order.email.order_approved': _(
            'An email has been sent to notify the user that the order has been approved.'
        ),
        'eventyay.event.order.email.order_placed': _(
            'An email has been sent to notify the user that the order has been received and requires payment.'
        ),
        'eventyay.event.order.email.order_placed_require_approval': _(
            'An email has been sent to notify the user that the order has been received and requires approval.'
        ),
        'eventyay.event.order.email.resend': _(
            'An email with a link to the order detail page has been resent to the user.'
        ),
        'eventyay.event.order.payment.confirmed': _('Payment {local_id} has been confirmed.'),
        'eventyay.event.order.payment.canceled': _('Payment {local_id} has been canceled.'),
        'eventyay.event.order.payment.canceled.failed': _('Canceling payment {local_id} has failed.'),
        'eventyay.event.order.payment.started': _('Payment {local_id} has been started.'),
        'eventyay.event.order.payment.failed': _('Payment {local_id} has failed.'),
        'eventyay.event.order.quotaexceeded': _('The order could not be marked as paid: {message}'),
        'eventyay.event.order.overpaid': _('The order has been overpaid.'),
        'eventyay.event.order.refund.created': _('Refund {local_id} has been created.'),
        'eventyay.event.order.refund.created.externally': _(
            'Refund {local_id} has been created by an external entity.'
        ),
        'eventyay.event.order.refund.requested': _('The customer requested you to issue a refund.'),
        'eventyay.event.order.refund.done': _('Refund {local_id} has been completed.'),
        'eventyay.event.order.refund.canceled': _('Refund {local_id} has been canceled.'),
        'eventyay.event.order.refund.failed': _('Refund {local_id} has failed.'),
        'eventyay.control.auth.user.created': _('The user has been created.'),
        'eventyay.user.settings.2fa.enabled': _('Two-factor authentication has been enabled.'),
        'eventyay.user.settings.2fa.disabled': _('Two-factor authentication has been disabled.'),
        'eventyay.user.settings.2fa.regenemergency': _('Your two-factor emergency codes have been regenerated.'),
        'eventyay.user.settings.2fa.device.added': _(
            'A new two-factor authentication device "{name}" has been added to your account.'
        ),
        'eventyay.user.settings.2fa.device.deleted': _(
            'The two-factor authentication device "{name}" has been removed from your account.'
        ),
        'eventyay.user.settings.notifications.enabled': _('Notifications have been enabled.'),
        'eventyay.user.settings.notifications.disabled': _('Notifications have been disabled.'),
        'eventyay.user.settings.notifications.changed': _('Your notification settings have been changed.'),
        'eventyay.user.anonymized': _('This user has been anonymized.'),
        'eventyay.user.oauth.authorized': _(
            'The application "{application_name}" has been authorized to access your account.'
        ),
        'eventyay.control.auth.user.forgot_password.mail_sent': _('Password reset mail sent.'),
        'eventyay.control.auth.user.forgot_password.recovered': _('The password has been reset.'),
        'eventyay.control.auth.user.forgot_password.denied.repeated': _(
            'A repeated password reset has been denied, as the last request was less than 24 hours ago.'
        ),
        'eventyay.organizer.deleted': _('The organizer "{name}" has been deleted.'),
        'eventyay.voucher.added': _('The voucher has been created.'),
        'eventyay.voucher.sent': _('The voucher has been sent to {recipient}.'),
        'eventyay.voucher.added.waitinglist': _(
            'The voucher has been created and sent to a person on the waiting list.'
        ),
        'eventyay.voucher.changed': _('The voucher has been changed.'),
        'eventyay.voucher.deleted': _('The voucher has been deleted.'),
        'eventyay.voucher.redeemed': _('The voucher has been redeemed in order {order_code}.'),
        'eventyay.event.product.added': _('The product has been created.'),
        'eventyay.event.product.changed': _('The product has been changed.'),
        'eventyay.event.product.deleted': _('The product has been deleted.'),
        'eventyay.event.product.variation.added': _('The variation "{value}" has been created.'),
        'eventyay.event.product.variation.deleted': _('The variation "{value}" has been deleted.'),
        'eventyay.event.product.variation.changed': _('The variation "{value}" has been changed.'),
        'eventyay.event.product.addons.added': _('An add-on has been added to this product.'),
        'eventyay.event.product.addons.removed': _('An add-on has been removed from this product.'),
        'eventyay.event.product.addons.changed': _('An add-on has been changed on this product.'),
        'eventyay.event.product.bundles.added': _('A bundled product has been added to this product.'),
        'eventyay.event.product.bundles.removed': _('A bundled product has been removed from this product.'),
        'eventyay.event.product.bundles.changed': _('A bundled product has been changed on this product.'),
        'eventyay.event.quota.added': _('The quota has been added.'),
        'eventyay.event.quota.deleted': _('The quota has been deleted.'),
        'eventyay.event.quota.changed': _('The quota has been changed.'),
        'eventyay.event.quota.closed': _('The quota has closed.'),
        'eventyay.event.quota.opened': _('The quota has been re-opened.'),
        'eventyay.event.category.added': _('The category has been added.'),
        'eventyay.event.category.deleted': _('The category has been deleted.'),
        'eventyay.event.category.changed': _('The category has been changed.'),
        'eventyay.event.question.added': _('The question has been added.'),
        'eventyay.event.question.deleted': _('The question has been deleted.'),
        'eventyay.event.question.changed': _('The question has been changed.'),
        'eventyay.event.taxrule.added': _('The tax rule has been added.'),
        'eventyay.event.taxrule.deleted': _('The tax rule has been deleted.'),
        'eventyay.event.taxrule.changed': _('The tax rule has been changed.'),
        'eventyay.event.checkinlist.added': _('The check-in list has been added.'),
        'eventyay.event.checkinlist.deleted': _('The check-in list has been deleted.'),
        'eventyay.event.checkinlist.changed': _('The check-in list has been changed.'),
        'eventyay.event.settings': _('The event settings have been changed.'),
        'eventyay.event.tickets.settings': _('The ticket download settings have been changed.'),
        'eventyay.event.plugins.enabled': _('A plugin has been enabled.'),
        'eventyay.event.plugins.disabled': _('A plugin has been disabled.'),
        'eventyay.event.live.activated': _('The shop has been taken live.'),
        'eventyay.event.live.deactivated': _('The shop has been taken offline.'),
        'eventyay.event.testmode.activated': _('The shop has been taken into test mode.'),
        'eventyay.event.testmode.deactivated': _('The test mode has been disabled.'),
        'eventyay.event.added': _('The event has been created.'),
        'eventyay.event.changed': _('The event details have been changed.'),
        'eventyay.event.question.option.added': _('An answer option has been added to the question.'),
        'eventyay.event.question.option.deleted': _('An answer option has been removed from the question.'),
        'eventyay.event.question.option.changed': _('An answer option has been changed.'),
        'eventyay.event.permissions.added': _('A user has been added to the event team.'),
        'eventyay.event.permissions.invited': _('A user has been invited to the event team.'),
        'eventyay.event.permissions.changed': _("A user's permissions have been changed."),
        'eventyay.event.permissions.deleted': _('A user has been removed from the event team.'),
        'eventyay.waitinglist.voucher': _('A voucher has been sent to a person on the waiting list.'),
        'eventyay.event.orders.waitinglist.deleted': _('An entry has been removed from the waiting list.'),
        'eventyay.event.orders.waitinglist.changed': _('An entry has been changed on the waiting list.'),
        'eventyay.event.orders.waitinglist.added': _('An entry has been added to the waiting list.'),
        'eventyay.team.created': _('The team has been created.'),
        'eventyay.team.changed': _('The team settings have been changed.'),
        'eventyay.team.deleted': _('The team has been deleted.'),
        'eventyay.gate.created': _('The gate has been created.'),
        'eventyay.gate.changed': _('The gate has been changed.'),
        'eventyay.gate.deleted': _('The gate has been deleted.'),
        'eventyay.subevent.deleted': pgettext_lazy('subevent', 'The event date has been deleted.'),
        'eventyay.subevent.canceled': pgettext_lazy('subevent', 'The event date has been canceled.'),
        'eventyay.subevent.changed': pgettext_lazy('subevent', 'The event date has been changed.'),
        'eventyay.subevent.added': pgettext_lazy('subevent', 'The event date has been created.'),
        'eventyay.subevent.quota.added': pgettext_lazy('subevent', 'A quota has been added to the event date.'),
        'eventyay.subevent.quota.changed': pgettext_lazy('subevent', 'A quota has been changed on the event date.'),
        'eventyay.subevent.quota.deleted': pgettext_lazy('subevent', 'A quota has been removed from the event date.'),
        'eventyay.device.created': _('The device has been created.'),
        'eventyay.device.changed': _('The device has been changed.'),
        'eventyay.device.revoked': _('Access of the device has been revoked.'),
        'eventyay.device.initialized': _('The device has been initialized.'),
        'eventyay.device.keyroll': _('The access token of the device has been regenerated.'),
        'eventyay.device.updated': _('The device has notified the server of an hardware or software update.'),
        'eventyay.giftcards.created': _('The gift card has been created.'),
        'eventyay.giftcards.modified': _('The gift card has been changed.'),
        'eventyay.giftcards.transaction.manual': _('A manual transaction has been performed.'),
    }

    data = json.loads(logentry.data)

    if logentry.action_type.startswith('eventyay.event.product.variation'):
        if 'value' not in data:
            # Backwards compatibility
            var = ProductVariation.objects.filter(id=data['id']).first()
            if var:
                data['value'] = str(var.value)
            else:
                data['value'] = '?'
        else:
            data['value'] = LazyI18nString(data['value'])

    if logentry.action_type in plains:
        data = defaultdict(lambda: '?', data)
        return plains[logentry.action_type].format_map(data)

    if logentry.action_type.startswith('eventyay.event.order.changed'):
        return _display_order_changed(sender, logentry)

    if logentry.action_type.startswith('eventyay.event.payment.provider.'):
        return _('The settings of a payment provider have been changed.')

    if logentry.action_type.startswith('eventyay.event.tickets.provider.'):
        return _('The settings of a ticket output provider have been changed.')

    if logentry.action_type == 'eventyay.event.order.consent':
        return _('The user confirmed the following message: "{}"').format(
            bleach.clean(logentry.parsed_data.get('msg'), tags=[], strip=True)
        )

    if sender and logentry.action_type.startswith('eventyay.event.checkin'):
        return _display_checkin(sender, logentry)

    if logentry.action_type == 'eventyay.control.views.checkin':
        # deprecated
        dt = dateutil.parser.parse(data.get('datetime'))
        tz = pytz.timezone(sender.settings.timezone)
        dt_formatted = date_format(dt.astimezone(tz), 'SHORT_DATETIME_FORMAT')
        if 'list' in data:
            try:
                checkin_list = sender.checkin_lists.get(pk=data.get('list')).name
            except CheckinList.DoesNotExist:
                checkin_list = _('(unknown)')
        else:
            checkin_list = _('(unknown)')

        if data.get('first'):
            return _('Position #{posid} has been checked in manually at {datetime} on list "{list}".').format(
                posid=data.get('positionid'),
                datetime=dt_formatted,
                list=checkin_list,
            )
        return _('Position #{posid} has been checked in again at {datetime} on list "{list}".').format(
            posid=data.get('positionid'), datetime=dt_formatted, list=checkin_list
        )

    if logentry.action_type in (
        'eventyay.control.views.checkin.reverted',
        'eventyay.event.checkin.reverted',
    ):
        if 'list' in data:
            try:
                checkin_list = sender.checkin_lists.get(pk=data.get('list')).name
            except CheckinList.DoesNotExist:
                checkin_list = _('(unknown)')
        else:
            checkin_list = _('(unknown)')

        return _('The check-in of position #{posid} on list "{list}" has been reverted.').format(
            posid=data.get('positionid'),
            list=checkin_list,
        )

    if logentry.action_type == 'eventyay.team.member.added':
        return _('{user} has been added to the team.').format(user=data.get('email'))

    if logentry.action_type == 'eventyay.team.member.removed':
        return _('{user} has been removed from the team.').format(user=data.get('email'))

    if logentry.action_type == 'eventyay.team.member.joined':
        return _('{user} has joined the team using the invite sent to {email}.').format(
            user=data.get('email'), email=data.get('invite_email')
        )

    if logentry.action_type == 'eventyay.team.invite.created':
        return _('{user} has been invited to the team.').format(user=data.get('email'))

    if logentry.action_type == 'eventyay.team.invite.resent':
        return _('Invite for {user} has been resent.').format(user=data.get('email'))

    if logentry.action_type == 'eventyay.team.invite.deleted':
        return _('The invite for {user} has been revoked.').format(user=data.get('email'))

    if logentry.action_type == 'eventyay.team.token.created':
        return _('The token "{name}" has been created.').format(name=data.get('name'))

    if logentry.action_type == 'eventyay.team.token.deleted':
        return _('The token "{name}" has been revoked.').format(name=data.get('name'))

    if logentry.action_type == 'eventyay.user.settings.changed':
        text = str(_('Your account settings have been changed.'))
        if 'email' in data:
            text = text + ' ' + str(_('Your email address has been changed to {email}.').format(email=data['email']))
        if 'new_pw' in data:
            text = text + ' ' + str(_('Your password has been changed.'))
        if data.get('is_active') is True:
            text = text + ' ' + str(_('Your account has been enabled.'))
        elif data.get('is_active') is False:
            text = text + ' ' + str(_('Your account has been disabled.'))
        return text

    if logentry.action_type == 'eventyay.control.auth.user.impersonated':
        return str(_('You impersonated {}.')).format(data['other_email'])

    if logentry.action_type == 'eventyay.control.auth.user.impersonate_stopped':
        return str(_('You stopped impersonating {}.')).format(data['other_email'])
