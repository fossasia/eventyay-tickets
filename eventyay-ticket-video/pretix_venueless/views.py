import datetime
import jwt
from django import forms
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.utils.translation import gettext, gettext_lazy as _
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from i18nfield.forms import I18nFormField
from pretix.base.forms import (
    I18nMarkdownTextarea, SecretKeySettingsField, SettingsForm,
)
from pretix.base.models import CheckinList, Event, Item, Order, Question
from pretix.base.reldate import RelativeDateTimeField
from pretix.base.services.checkin import perform_checkin
from pretix.control.views.event import (
    EventSettingsFormView, EventSettingsViewMixin,
)
from pretix.presale.views import EventViewMixin
from pretix.presale.views.order import OrderPositionDetailMixin


class VenuelessSettingsForm(SettingsForm):
    venueless_url = forms.URLField(
        label=_("Eventyay Video URL"),
        required=False,
    )
    venueless_secret = SecretKeySettingsField(
        label=_("Eventyay Video secret"),
        required=False,
    )
    venueless_issuer = forms.CharField(
        label=_("Eventyay Video issuer"),
        required=False,
    )
    venueless_audience = forms.CharField(
        label=_("Eventyay Video audience"),
        required=False,
    )
    venueless_start = RelativeDateTimeField(
        label=_('Do not allow access before'),
        required=False,
    )
    venueless_allow_pending = forms.BooleanField(
        label=_('Allow users to access the live event before their order is paid'),
        required=False,
    )
    venueless_all_items = forms.BooleanField(
        label=_('Allow buyers of all admission products'),
        required=False
    )
    venueless_items = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(
            attrs={
                'class': 'scrolling-multiple-choice',
                'data-inverse-dependency': '<[name$=venueless_all_items]'
            }
        ),
        label=_('Limit to products'),
        required=False,
        queryset=Item.objects.none(),
        initial=None
    )
    venueless_questions = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(
            attrs={
                'class': 'scrolling-multiple-choice',
            }
        ),
        label=_('Transmit answers to questions'),
        required=False,
        queryset=Question.objects.none(),
        initial=None
    )
    venueless_text = I18nFormField(
        label=_('Introductory text'),
        required=False,
        widget=I18nMarkdownTextarea,
    )
    venueless_talk_schedule_url = forms.URLField(
        label=_("Eventyay schedule URL"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        event = kwargs['obj']
        super().__init__(*args, **kwargs)
        self.fields['venueless_items'].queryset = event.items.all()
        self.fields['venueless_questions'].queryset = event.questions.all()

    def clean(self):
        data = super().clean()

        for k, v in self.fields.items():
            if isinstance(v, forms.ModelMultipleChoiceField):
                answstr = [o.pk for o in data[k]]
                data[k] = answstr

        return data


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
        profile = {
            'fields': {}
        }
        if self.position.attendee_name:
            profile['display_name'] = self.position.attendee_name
        if self.position.company:
            profile['fields']['company'] = self.position.company

        for a in self.position.answers.filter(question_id__in=request.event.settings.venueless_questions).select_related('question'):
            profile['fields'][a.question.identifier] = a.answer

        uid_token = self.order.customer.identifier if self.order.customer else self.position.pseudonymization_id

        payload = {
            "iss": request.event.settings.venueless_issuer,
            "aud": request.event.settings.venueless_audience,
            "exp": exp,
            "iat": iat,
            "uid": uid_token,
            "profile": profile,
            "traits": list(
                {
                    'eventyay-video-event-{}'.format(request.event.slug),
                    'eventyay-video-subevent-{}'.format(self.position.subevent_id),
                    'eventyay-video-item-{}'.format(self.position.item_id),
                    'eventyay-video-variation-{}'.format(self.position.variation_id),
                    'eventyay-video-category-{}'.format(self.position.item.category_id),
                } | {
                    'eventyay-video-item-{}'.format(p.item_id)
                    for p in self.position.addons.all()
                } | {
                    'eventyay-video-variation-{}'.format(p.variation_id)
                    for p in self.position.addons.all() if p.variation_id
                } | {
                    'eventyay-video-category-{}'.format(p.item.category_id)
                    for p in self.position.addons.all() if p.item.category_id
                }
            )
        }
        token = jwt.encode(
            payload, self.request.event.settings.venueless_secret, algorithm="HS256"
        )

        cl = CheckinList.objects.get_or_create(
            event=self.request.event,
            subevent=self.position.subevent,
            name=gettext('Eventyay Video'),
            defaults={
                'all_products': True,
                'include_pending': self.request.event.settings.venueless_allow_pending,
            }
        )[0]
        try:
            perform_checkin(self.position, cl, {})
        except:
            pass

        baseurl = self.request.event.settings.venueless_url
        if kwargs.get("view_schedule") == 'True':
            return redirect(self.request.event.settings.venueless_talk_schedule_url)
        if '{token}' in baseurl:
            # Hidden feature to support other kinds of installations
            return redirect(baseurl.format(token=token))
        return redirect('{}/#token={}'.format(baseurl, token).replace("//#", "/#"))
