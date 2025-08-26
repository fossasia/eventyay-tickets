from django.utils.translation import gettext_lazy as _


class FullAccessSecurityProfile:
    identifier = 'full'
    verbose_name = _(
        'Full device access (reading and changing orders and gift cards, reading of products and settings)'
    )

    def is_allowed(self, request):
        return True


class AllowListSecurityProfile:
    allowlist = ()

    def is_allowed(self, request):
        key = (
            request.method,
            f'{request.resolver_match.namespace}:{request.resolver_match.url_name}',
        )
        return key in self.allowlist


class EventyayCheckinSecurityProfile(AllowListSecurityProfile):
    identifier = 'eventyay_checkin'
    verbose_name = _('eventyay_checkin')
    allowlist = (
        ('GET', 'api-v1:version'),
        ('GET', 'api-v1:device.eventselection'),
        ('POST', 'api-v1:device.update'),
        ('POST', 'api-v1:device.revoke'),
        ('POST', 'api-v1:device.roll'),
        ('GET', 'api-v1:event-list'),
        ('GET', 'api-v1:event-detail'),
        ('GET', 'api-v1:subevent-list'),
        ('GET', 'api-v1:subevent-detail'),
        ('GET', 'api-v1:itemcategory-list'),
        ('GET', 'api-v1:item-list'),
        ('GET', 'api-v1:question-list'),
        ('GET', 'api-v1:badgelayout-list'),
        ('GET', 'api-v1:badgeitem-list'),
        ('GET', 'api-v1:checkinlist-list'),
        ('GET', 'api-v1:checkinlist-status'),
        ('GET', 'api-v1:checkinlistpos-list'),
        ('POST', 'api-v1:checkinlistpos-redeem'),
        ('GET', 'api-v1:revokedsecrets-list'),
        ('GET', 'api-v1:order-list'),
        ('GET', 'api-v1:orderposition-pdf_image'),
        ('GET', 'api-v1:event.settings'),
        ('POST', 'api-v1:upload'),
    )


class EventyayCheckinNoSyncSecurityProfile(AllowListSecurityProfile):
    identifier = 'eventyay_checkin_online_kiosk'
    verbose_name = _('eventyay_checkin (kiosk mode, online only)')
    allowlist = (
        ('GET', 'api-v1:version'),
        ('GET', 'api-v1:device.eventselection'),
        ('POST', 'api-v1:device.update'),
        ('POST', 'api-v1:device.revoke'),
        ('POST', 'api-v1:device.roll'),
        ('GET', 'api-v1:event-list'),
        ('GET', 'api-v1:event-detail'),
        ('GET', 'api-v1:subevent-list'),
        ('GET', 'api-v1:subevent-detail'),
        ('GET', 'api-v1:itemcategory-list'),
        ('GET', 'api-v1:item-list'),
        ('GET', 'api-v1:question-list'),
        ('GET', 'api-v1:badgelayout-list'),
        ('GET', 'api-v1:badgeitem-list'),
        ('GET', 'api-v1:checkinlist-list'),
        ('GET', 'api-v1:checkinlist-status'),
        ('POST', 'api-v1:checkinlistpos-redeem'),
        ('GET', 'api-v1:revokedsecrets-list'),
        ('GET', 'api-v1:orderposition-pdf_image'),
        ('GET', 'api-v1:event.settings'),
        ('POST', 'api-v1:upload'),
    )


DEVICE_SECURITY_PROFILES = {
    k.identifier: k()
    for k in (
        FullAccessSecurityProfile,
        EventyayCheckinSecurityProfile,
        EventyayCheckinNoSyncSecurityProfile,
    )
}
