from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import pgettext_lazy
from django_scopes.forms import SafeModelMultipleChoiceField

from pretix.api.models import WebHook
from pretix.api.webhooks import get_all_webhook_events


class WebHookForm(forms.ModelForm):
    events = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, label=pgettext_lazy('webhooks', 'Event types'))

    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer')
        super().__init__(*args, **kwargs)
        self.fields['limit_events'].queryset = organizer.events.all()
        self.fields['events'].choices = [
            (a.action_type, mark_safe('{} – <code>{}</code>'.format(a.verbose_name, a.action_type))) for a in get_all_webhook_events().values()
        ]
        if self.instance and self.instance.pk:
            self.fields['events'].initial = list(self.instance.listeners.values_list('action_type', flat=True))

    class Meta:
        model = WebHook
        fields = ['target_url', 'enabled', 'all_events', 'limit_events']
        widgets = {
            'limit_events': forms.CheckboxSelectMultiple(attrs={'data-inverse-dependency': '#id_all_events'}),
        }
        field_classes = {'limit_events': SafeModelMultipleChoiceField}
