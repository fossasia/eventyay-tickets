from decimal import Decimal

from django import forms
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from django.views import View
from formtools.wizard.views import NamedUrlSessionWizardView
from pretalx.cfp.views.event import EventPageMixin
from pretalx.submission.models import QuestionVariant


class InfoStepForm(forms.Form):
    title = forms.CharField(max_length=200)
    subtitle = forms.CharField(max_length=300)
    abstract = forms.CharField(widget=forms.Textarea)


class QuestionStepForm(forms.Form):

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)

        super().__init__(*args, **kwargs)

        for q in event.questions.prefetch_related('options'):
            if q.variant == QuestionVariant.BOOLEAN:
                if q.required:
                    # For some reason, django-bootstrap4 does not set the required attribute
                    # itself.
                    widget = forms.CheckboxInput(attrs={'required': 'required'})
                else:
                    widget = forms.CheckboxInput()

                field = forms.BooleanField(
                    label=q.question, required=q.required,
                    widget=widget, initial=bool(q.default_answer)
                )
            elif q.variant == QuestionVariant.NUMBER:
                field = forms.DecimalField(
                    label=q.question, required=q.required,
                    min_value=Decimal('0.00'), initial=q.default_answer
                )
            elif q.variant == QuestionVariant.STRING:
                field = forms.CharField(
                    label=q.question, required=q.required, initial=q.default_answer
                )
            elif q.variant == QuestionVariant.TEXT:
                field = forms.CharField(
                    label=q.question, required=q.required,
                    widget=forms.Textarea,
                    initial=q.default_answer
                )
            elif q.variant == QuestionVariant.CHOICES:
                field = forms.ModelChoiceField(
                    queryset=q.options.all(),
                    label=q.question, required=q.required,
                    widget=forms.RadioSelect,
                    initial=q.default_answer
                )
            elif q.variant == QuestionVariant.MULTIPLE:
                field = forms.ModelMultipleChoiceField(
                    queryset=q.options.all(),
                    label=q.question, required=q.required,
                    widget=forms.CheckboxSelectMultiple,
                    initial=q.default_answer
                )
            field.question = q
            self.fields['question_%s' % q.id] = field


class UserStepForm(forms.Form):
    login_username = forms.CharField(max_length=60, label=_('Username or email address'),
                                     required=False)
    login_password = forms.CharField(widget=forms.PasswordInput, label=_('Password'),
                                     required=False)
    register_username = forms.CharField(max_length=60, label=_('Username'),
                                        required=False)
    register_email = forms.CharField(max_length=60, label=_('Email address'),
                                     required=False)
    register_password = forms.CharField(widget=forms.PasswordInput, label=_('Password'),
                                        required=False)
    register_password_repeat = forms.CharField(widget=forms.PasswordInput, label=_('Password (again)'),
                                               required=False)


FORMS = [
    ("info", InfoStepForm),
    ("questions", QuestionStepForm),
    ("user", UserStepForm),
]

TEMPLATES = {
    "info": "cfp/event/submission_info.html",
    "questions": "cfp/event/submission_questions.html",
    "user": "cfp/event/submission_user.html",
}


class SubmitStartView(EventPageMixin, View):

    def get(self, request, *args, **kwargs):
        newid = get_random_string(length=6)
        return redirect(reverse('cfp:event.submit', kwargs={
            'event': request.event.slug,
            'step': 'info',
            'tmpid': newid
        }))


def show_questions_page(wizard):
    return wizard.request.event.questions.exists()


class SubmitWizard(EventPageMixin, NamedUrlSessionWizardView):
    form_list = FORMS
    condition_dict = {
        'questions': show_questions_page
    }

    def get_form_instance(self, step):
        return super().get_form_instance(step)

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        if step == 'questions':
            kwargs['event'] = self.request.event
        return kwargs

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def get_prefix(self, request, *args, **kwargs):
        return super().get_prefix(request, *args, **kwargs) + ':' + kwargs.get('tmpid')

    def get_step_url(self, step):
        return reverse(self.url_name, kwargs={
            'step': step,
            'tmpid': self.kwargs.get('tmpid'),
            'event': self.kwargs.get('event')
        })

    def done(self, form_list, **kwargs):
        return render(self.request, 'done.html', {
            'form_data': [form.cleaned_data for form in form_list],
        })
