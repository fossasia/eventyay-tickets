from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from django.views import View
from formtools.wizard.views import NamedUrlSessionWizardView

from pretalx.cfp.views.event import EventPageMixin
from pretalx.person.models import User
from pretalx.submission.models import (
    Answer, Question, QuestionVariant, Submission,
)


class InfoStepForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['title', 'subtitle', 'submission_type', 'description', 'abstract', 'notes', 'duration']


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
    login_username = forms.CharField(max_length=60,
                                     label=_('Username or email address'),
                                     required=False)
    login_password = forms.CharField(widget=forms.PasswordInput,
                                     label=_('Password'),
                                     required=False)
    register_username = forms.CharField(max_length=60,
                                        label=_('Username'),
                                        required=False)
    register_email = forms.EmailField(label=_('Email address'),
                                      required=False)
    register_password = forms.CharField(widget=forms.PasswordInput,
                                        label=_('Password'),
                                        required=False)
    register_password_repeat = forms.CharField(widget=forms.PasswordInput,
                                               label=_('Password (again)'),
                                               required=False)

    def clean(self):
        data = super().clean()

        if data.get('login_username') and data.get('login_password'):
            if '@' in data.get('login_username'):
                try:
                    uname = User.objects.get(email=data.get('login_username')).nick
                except User.DoesNotExist:
                    uname = 'user@invalid'
            else:
                uname = data.get('login_username')

            user = authenticate(username=uname, password=data.get('login_password'))

            if user is None:
                raise ValidationError(_('No user account matches the entered credentials. '
                                        'Are you sure that you typed your password correctly?'))

            if not user.is_active:
                raise ValidationError(_('Sorry, your account is currently disabled.'))

            data['user_id'] = user.pk

        elif data.get('register_username') and data.get('register_email') and data.get('register_password'):
            if data.get('register_password') != data.get('register_password_repeat'):
                raise ValidationError(_('You entered two different passwords. Please input the same one twice!'))

            if User.objects.filter(nick=data.get('register_username')).exists():
                raise ValidationError(_('We already have a user with that username. Did you already register before '
                                        'and just need to log in?'))

            if User.objects.filter(email=data.get('register_email')).exists():
                raise ValidationError(_('We already have a user with that email address. Did you already register '
                                        'before and just need to log in?'))

            user = User.objects.create_user(nick=data.get('register_username'),
                                            email=data.get('register_email'),
                                            password=data.get('register_password'))
            data['user_id'] = user.pk
        else:
            raise ValidationError(
                _('You need to fill all fields of either the login or the registration form.')
            )

        return data


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

    def done(self, form_list, form_dict, **kwargs):
        user = User.objects.get(pk=form_dict['user'].cleaned_data['user_id'])

        form_dict['info'].instance.event = self.request.event
        form_dict['info'].save()
        form_dict['info'].instance.speakers.add(user)
        sub = form_dict['info'].instance

        if 'questions' in form_dict:
            for k, value in form_dict['questions'].cleaned_data.items():
                qid = k.split('_')[1]
                question = Question.objects.get(pk=qid)
                answer = Answer(question=question, submission=sub)

                if question.variant == QuestionVariant.MULTIPLE:
                    answstr = ", ".join([str(o) for o in value])
                    answer.save()
                    answer.answer = answstr
                    answer.options.add(*value)
                elif question.variant == QuestionVariant.CHOICES:
                    answer.save()
                    answer.options.add(value)
                    answer.answer = value.answer
                else:
                    answer.answer = value
                answer.save()

        login(self.request, user)

        # TODO: Redirect to detail page of submission
        return redirect(reverse('cfp:event.thanks', kwargs={
            'event': self.request.event.slug
        }))
