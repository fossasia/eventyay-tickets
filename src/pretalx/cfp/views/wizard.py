import logging
import os

from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.files.storage import FileSystemStorage
from django.db.models import Q
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
from pretalx.common.mixins.views import SensibleBackWizardMixin
from pretalx.common.phrases import phrases
from pretalx.mail.context import template_context_from_submission
from pretalx.mail.models import MailTemplate
from pretalx.person.forms import SpeakerProfileForm, UserForm
from pretalx.person.models import User
from pretalx.submission.forms import InfoForm, QuestionsForm
from pretalx.submission.models import Answer, QuestionTarget, QuestionVariant, SubmissionType, Track

FORMS = [
    ('info', InfoForm),
    ('questions', QuestionsForm),
    ('user', UserForm),
    ('profile', SpeakerProfileForm),
]
FORM_DATA = {
    'info': {'label': _('General'), 'icon': 'paper-plane'},
    'questions': {'label': _('Questions'), 'icon': 'question-circle-o'},
    'user': {'label': _('Account'), 'icon': 'user-circle-o'},
    'profile': {'label': _('Profile'), 'icon': 'address-card-o'},
}


class SubmitStartView(EventPageMixin, View):

    @staticmethod
    def get(request, *args, **kwargs):
        url = reverse(
            'cfp:event.submit',
            kwargs={
                'event': request.event.slug,
                'step': 'info',
                'tmpid': get_random_string(length=6),
            },
        )
        if request.GET:
            url += f'?{request.GET.urlencode()}'
        return redirect(url)


def show_questions_page(wizard):
    info_data = wizard.get_cleaned_data_for_step('info')
    if not info_data or not info_data.get('track'):
        return wizard.request.event.questions.all().exists()
    return wizard.request.event.questions.exclude(
        Q(target=QuestionTarget.SUBMISSION)
        & (
            ~Q(tracks__in=[info_data.get('track')])
            & Q(tracks__isnull=False)
        )
    ).exists()


def show_user_page(wizard):
    return not wizard.request.user.is_authenticated


@method_decorator(csp_update(IMG_SRC="https://www.gravatar.com"), name='dispatch')
class SubmitWizard(EventPageMixin, SensibleBackWizardMixin, NamedUrlSessionWizardView):
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
            user_data = self.get_cleaned_data_for_step('user') or dict()
            if user_data and user_data.get('user_id'):
                kwargs['user'] = User.objects.filter(pk=user_data['user_id']).first()
            if not kwargs.get('user') and self.request.user.is_authenticated:
                kwargs['user'] = self.request.user
            user = kwargs.get('user')
            kwargs['name'] = user.name if user else user_data.get('register_name')
            kwargs['read_only'] = False
            kwargs['essential_only'] = True
        if step == 'questions':
            kwargs['target'] = ''
            kwargs['track'] = (self.get_cleaned_data_for_step('info') or dict()).get('track')
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        step = kwargs.get('step')
        form = kwargs.get('form')
        step_list = []
        phase = 'done'
        for stp, form_class in self.get_form_list().items():
            if stp == step or isinstance(form, form_class):
                phase = 'current'
            step_list.append(
                {
                    'url': self.get_step_url(stp),
                    'phase': phase,
                    'label': FORM_DATA[stp]['label'],
                    'icon': FORM_DATA[stp]['icon'],
                }
            )
            if phase == 'current':
                phase = 'todo'
        step_list.append({'phase': 'todo', 'label': _('Done!'), 'icon': 'check'})
        context['step_list'] = step_list

        if step == 'info':
            # use value of query string parameters track and submission_type as initial values for form if they are valid
            for field, model_name in (('submission_type', SubmissionType), ('track', Track)):
                request_value = self.request.GET.get(field)
                try:
                    request_id = model_name.id_from_slug(request_value) if request_value else None
                except:
                    continue
                # search requested object by ID
                obj = model_name.objects.filter(event=self.request.event, id=request_id).first()
                # ensure that the whole slug matches, not only the ID
                if obj and obj.slug() == request_value:
                    context['form'].initial[field] = obj
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
        if not user or not user.is_active:
            raise ValidationError(
                _(
                    'There was an error when logging in. Please contact the organiser for further help.'
                ),
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
                submission=sub,
                full_submission_content=True,
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
            additional_speaker = form_dict['info'].cleaned_data.get('additional_speaker')
            if additional_speaker:
                sub.send_invite(to=[additional_speaker], _from=user)
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
