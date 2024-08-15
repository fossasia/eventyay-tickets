import re

from django.conf import settings
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views import View

from pretix.base.i18n import language
from pretix.base.templatetags.rich_text import markdown_compile_email
from pretix.control.forms.organizer_forms import MailSettingsForm
from pretix.control.permissions import OrganizerPermissionRequiredMixin


class MailSettingsPreview(OrganizerPermissionRequiredMixin, View):
    permission = 'can_change_organizer_settings'

    class SafeDict(dict):
        def __missing__(self, key):
            return '{' + key + '}'

    @cached_property
    def supported_locale(self):
        locales = {}
        for idx, val in enumerate(settings.LANGUAGES):
            if val[0] in self.request.organizer.settings.locales:
                locales[str(idx)] = val[0]
        return locales

    def placeholders(self, item):
        ctx = {}
        for p, s in MailSettingsForm(obj=self.request.organizer)._get_sample_context(
                MailSettingsForm.base_context[item]).items():
            if s.strip().startswith('*'):
                ctx[p] = s
            else:
                ctx[p] = '<span class="placeholder" title="{}">{}</span>'.format(
                    _('This value will be replaced based on dynamic parameters.'),
                    s
                )
        return self.SafeDict(ctx)

    def post(self, request, *args, **kwargs):
        """
        Handles the POST request to generate a preview of email messages in different locales.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            JsonResponse: A JSON response containing the item and the compiled messages for each locale.
            HttpResponseBadRequest: If the preview item is invalid.
        """
        preview_item = request.POST.get('item', '')
        if preview_item not in MailSettingsForm.base_context:
            return HttpResponseBadRequest(_('Invalid item'))

        regex = r"^" + re.escape(preview_item) + r"_(?P<idx>[\d+])$"
        msgs = {}

        for k, v in request.POST.items():
            matched = re.search(regex, k)
            if matched:
                idx = matched.group('idx')
                if idx in self.supported_locale:
                    with language(self.supported_locale[idx], self.request.organizer.settings.region):
                        msgs[self.supported_locale[idx]] = markdown_compile_email(
                            v.format_map(self.placeholders(preview_item))
                        )

        return JsonResponse({
            'item': preview_item,
            'msgs': msgs
        })
