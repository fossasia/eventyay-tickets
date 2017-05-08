from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from django.views import View
from formtools.wizard.views import NamedUrlSessionWizardView

from pretalx.cfp.forms.submissions import InfoForm, QuestionsForm
from pretalx.cfp.views.event import EventPageMixin
from pretalx.mail.context import template_context_from_submission
from pretalx.person.forms import SpeakerProfileForm, UserForm
from pretalx.person.models import User
from pretalx.submission.models import Answer, Question, QuestionVariant

FORMS = [
    ("info", InfoForm),
    ("questions", QuestionsForm),
    ("user", UserForm),
    ("profile", SpeakerProfileForm),
]

TEMPLATES = {
    "info": "cfp/event/submission_info.html",
    "questions": "cfp/event/submission_questions.html",
    "user": "cfp/event/submission_user.html",
    "profile": "cfp/event/submission_profile.html",
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


def show_user_page(wizard):
    return not wizard.request.user.is_authenticated


class SubmitWizard(EventPageMixin, NamedUrlSessionWizardView):
    form_list = FORMS
    condition_dict = {
        'questions': show_questions_page,
        'user': show_user_page
    }

    def get(self, request, *args, **kwargs):
        if not request.event.cfp.is_open:
            messages.error(request, _('This event currently does not accept new submissions, sorry!'))
            return redirect(reverse('cfp:event.start', kwargs={'event': request.event.slug}))
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not request.event.cfp.is_open:
            messages.error(request, _('This event currently does not accept new submissions, sorry!'))
            return redirect(reverse('cfp:event.start', kwargs={'event': request.event.slug}))
        return super().post(request, *args, **kwargs)

    def get_form_instance(self, step):
        return super().get_form_instance(step)

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        if step in ['info', 'profile', 'questions']:
            kwargs['event'] = self.request.event
        if step == 'profile':
            user_data = self.get_cleaned_data_for_step('user')
            if user_data and user_data.get('user_id'):
                kwargs['user'] = User.objects.get(pk=user_data['user_id'])
            elif self.request.user.is_authenticated:
                kwargs['user'] = self.request.user
            kwargs['read_only'] = False
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
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            uid = form_dict['user'].save()
            user = User.objects.get(pk=uid)

        form_dict['info'].instance.event = self.request.event
        form_dict['info'].save()
        form_dict['info'].instance.speakers.add(user)
        sub = form_dict['info'].instance
        form_dict['profile'].user = user
        form_dict['profile'].save()
        sub.event.ack_template.to_mail(
            user=user, event=self.request.event, context=template_context_from_submission(sub),
            skip_queue=True, locale=user.locale
        )

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

        sub.log_action('pretalx.submission.create', person=user)
        messages.success(self.request, 'Your talk has been submitted successfully!')
        login(self.request, user)
        return redirect(reverse('cfp:event.user.submissions', kwargs={
            'event': self.request.event.slug
        }))
