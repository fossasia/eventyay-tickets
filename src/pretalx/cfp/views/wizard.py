import logging
import os

from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.files.storage import FileSystemStorage
from django.forms import ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views import View
from formtools.wizard.views import NamedUrlSessionWizardView

from pretalx.cfp.views.event import EventPageMixin
from pretalx.common.mail import SendMailException
from pretalx.common.phrases import phrases
from pretalx.mail.context import template_context_from_submission
from pretalx.mail.models import MailTemplate
from pretalx.person.forms import SpeakerProfileForm, UserForm
from pretalx.person.models import User
from pretalx.submission.forms import InfoForm, QuestionsForm
from pretalx.submission.models import Answer, QuestionTarget, QuestionVariant

FORMS = [
    ('info', InfoForm),
    ('questions', QuestionsForm),
    ('user', UserForm),
    ('profile', SpeakerProfileForm),
]


class SubmitStartView(EventPageMixin, View):
    @staticmethod
    def get(request, *args, **kwargs):
        return redirect(
            reverse(
                'cfp:event.submit',
                kwargs={
                    'event': request.event.slug,
                    'step': 'info',
                    'tmpid': get_random_string(length=6),
                },
            )
        )


def show_questions_page(wizard):
    return wizard.request.event.questions.all().exists()


def show_user_page(wizard):
    return not wizard.request.user.is_authenticated


@method_decorator(csp_update(IMG_SRC="https://www.gravatar.com"), name='dispatch')
class SubmitWizard(EventPageMixin, NamedUrlSessionWizardView):
    form_list = FORMS
    condition_dict = {'questions': show_questions_page, 'user': show_user_page}
    file_storage = FileSystemStorage(os.path.join(settings.MEDIA_ROOT, 'avatars'))

    def dispatch(self, request, *args, **kwargs):
        if not request.event.cfp.is_open:
            messages.error(request, phrases.cfp.submissions_closed)
            return redirect(
                reverse('cfp:event.start', kwargs={'event': request.event.slug})
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        if step in ['info', 'profile', 'questions']:
            kwargs['event'] = self.request.event
        if step == 'profile':
            user_data = self.get_cleaned_data_for_step('user')
            if user_data and user_data.get('user_id'):
                kwargs['user'] = User.objects.filter(pk=user_data['user_id']).first()
            if not kwargs.get('user') and self.request.user.is_authenticated:
                kwargs['user'] = self.request.user
            kwargs['read_only'] = False
            kwargs['essential_only'] = True
        if step == 'questions':
            kwargs['target'] = ''
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        step = kwargs.get('step')
        if step == 'profile':
            if hasattr(self.request.user, 'email'):
                email = self.request.user.email
            else:
                data = self.get_cleaned_data_for_step('user') or dict()
                email = data.get('register_email', '')
            context['gravatar_parameter'] = User(email=email).gravatar_parameter
        return context

    def get_template_names(self):
        return f'cfp/event/submission_{self.steps.current}.html'

    def get_prefix(self, request, *args, **kwargs):
        return super().get_prefix(request, *args, **kwargs) + ':' + kwargs.get('tmpid')

    def get_step_url(self, step):
        return reverse(
            self.url_name,
            kwargs={
                'step': step,
                'tmpid': self.kwargs.get('tmpid'),
                'event': self.kwargs.get('event'),
            },
        )

    def _handle_question_answer(self, sub, qid, value, user=None):
        question = self.request.event.questions.filter(pk=qid).first()
        if not question:
            return
        if question.target == QuestionTarget.SUBMISSION:
            answer = Answer(question=question, submission=sub)
        elif question.target == QuestionTarget.SPEAKER:
            answer = Answer(question=question, person=user)

        if question.variant == QuestionVariant.MULTIPLE:
            answstr = ', '.join([str(o) for o in value])
            answer.save()
            if value:
                answer.answer = answstr
                answer.options.add(*value)
        elif question.variant == QuestionVariant.CHOICES:
            answer.save()
            if value:
                answer.options.add(value)
                answer.answer = value.answer
        else:
            answer.answer = value or ''
        if answer.answer is not None:
            answer.save()

    def done(self, form_list, **kwargs):
        form_dict = kwargs.get('form_dict')
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            uid = form_dict['user'].save()
            user = User.objects.filter(pk=uid).first()
        if not user:
            raise ValidationError(
                _(
                    'There was an error with your user account. Please contact the organiser for further help.'
                )
            )

        form_dict['info'].instance.event = self.request.event
        form_dict['info'].save()
        form_dict['info'].instance.speakers.add(user)
        sub = form_dict['info'].instance
        form_dict['profile'].user = user
        form_dict['profile'].save()
        if 'questions' in form_dict:
            for k, value in form_dict['questions'].cleaned_data.items():
                qid = k.split('_')[1]
                self._handle_question_answer(sub, qid, value, user=user)

        try:
            sub.event.ack_template.to_mail(
                user=user,
                event=self.request.event,
                context=template_context_from_submission(sub),
                skip_queue=True,
                locale=user.locale,
            )
            if self.request.event.settings.mail_on_new_submission:
                MailTemplate(
                    event=self.request.event,
                    subject=_('New submission!').format(event=self.request.event.slug),
                    text=self.request.event.settings.mail_text_new_submission,
                ).to_mail(
                    user=self.request.event.email,
                    event=self.request.event,
                    context=template_context_from_submission(sub),
                    skip_queue=True,
                    locale=self.request.event.locale,
                )
        except SendMailException as exception:
            logging.getLogger('').warning(str(exception))
            messages.warning(self.request, phrases.cfp.submission_email_fail)

        sub.log_action('pretalx.submission.create', person=user)
        messages.success(self.request, phrases.cfp.submission_success)
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect(
            reverse(
                'cfp:event.user.submissions', kwargs={'event': self.request.event.slug}
            )
        )
