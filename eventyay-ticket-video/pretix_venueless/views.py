import datetime

import jwt
from django import forms
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt

from pretix.base.forms import SettingsForm, SecretKeySettingsField
from pretix.base.models import Event, Order
from pretix.base.reldate import RelativeDateTimeField
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin
from pretix.presale.views import EventViewMixin
from pretix.presale.views.order import OrderPositionDetailMixin


class VenuelessSettingsForm(SettingsForm):
    venueless_url = forms.URLField(
        label=_("Venueless URL"),
        required=False,
    )
    venueless_secret = SecretKeySettingsField(
        label=_("Venueless secret"),
        required=False,
    )
    venueless_issuer = forms.CharField(
        label=_("Venueless issuer"),
        required=False,
    )
    venueless_audience = forms.CharField(
        label=_("Venueless audience"),
        required=False,
    )
    venueless_start = RelativeDateTimeField(
        label=_('Start of live event'),
        required=False,
    )
    venueless_allow_pending = forms.BooleanField(
        label=_('Allow users to access the live event before their order is paid'),
        required=False,
    )


class SettingsView(EventSettingsViewMixin, EventSettingsFormView):
    model = Event
    form_class = VenuelessSettingsForm
    template_name = 'pretix_venueless/settings.html'
    permission = 'can_change_settings'

    def get_success_url(self) -> str:
        return reverse('plugins:pretix_venueless:settings', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


@method_decorator(xframe_options_exempt, 'dispatch')
class OrderPositionJoin(EventViewMixin, OrderPositionDetailMixin, View):

    def post(self, request, *args, **kwargs):
        if not self.position:
            raise Http404(_('Unknown order code or not authorized to access this order.'))

        forbidden = (
                (self.order.status != Order.STATUS_PAID and not (self.order.status == Order.STATUS_PENDING and
                                                                 request.event.settings.venueless_allow_pending))
                or self.position.canceled
                or not self.position.item.admission
        )
        if forbidden:
            raise PermissionDenied()

        if request.event.settings.venueless_start and request.event.settings.venueless_start.datetime(self.position.subevent or request.event) > now():
            raise PermissionDenied()

        iat = datetime.datetime.utcnow()
        exp = iat + datetime.timedelta(days=30)
        profile = None
        if self.position.attendee_name:
            profile = {
                "display_name": self.position.attendee_name
            }
        payload = {
            "iss": request.event.settings.venueless_issuer,
            "aud": request.event.settings.venueless_audience,
            "exp": exp,
            "iat": iat,
            "uid": self.position.pseudonymization_id,
            "profile": profile,
            "traits": list(
                {
                    'pretix-event-{}'.format(request.event.slug),
                    'pretix-subevent-{}'.format(self.position.subevent_id),
                    'pretix-item-{}'.format(self.position.item_id),
                    'pretix-variation-{}'.format(self.position.variation_id),
                    'pretix-category-{}'.format(self.position.item.category_id),
                } | {
                    'pretix-item-{}'.format(p.item_id)
                    for p in self.position.addons.all()
                } | {
                    'pretix-variation-{}'.format(p.variation_id)
                    for p in self.position.addons.all() if p.variation_id
                } | {
                    'pretix-category-{}'.format(p.item.category_id)
                    for p in self.position.addons.all() if p.item.category_id
                }
            )
        }
        token = jwt.encode(
            payload, self.request.event.settings.venueless_secret, algorithm="HS256"
        ).decode("utf-8")
        return redirect('{}/#token={}'.format(self.request.event.settings.venueless_url, token))
