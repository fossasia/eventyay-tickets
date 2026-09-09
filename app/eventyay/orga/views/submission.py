import json
from collections import Counter
from operator import itemgetter

from dateutil import rrule
from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.contrib.syndication.views import Feed
from django.db import transaction
from django.db.models import Count as DbCount, Prefetch, Q
from django.db.models.functions import TruncDate
from django.forms.models import BaseModelFormSet, inlineformset_factory
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import feedgenerator
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext, gettext_lazy as _
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View
from django_context_decorator import context
from urllib.parse import urlencode

from eventyay.base.models import (
    Answer,
    Feedback,
    LogEntry,
    Resource,
    ResourceKind,
    Submission,
    SubmissionComment,
    SubmissionStates,
    Tag,
    TalkQuestionTarget,
    User,
)
from eventyay.base.models.base import CachedFile
from eventyay.base.models.mail import MailTemplateRoles
from eventyay.base.models.profile import SpeakerProfile
from eventyay.base.services.etherpad import (
    EtherpadConfigurationError,
    EtherpadError,
    generate_pad_for_submission,
)
from eventyay.base.services.orderimport import parse_csv
from eventyay.base.services.talkimport import import_submissions
from eventyay.base.views.tasks import AsyncAction
from eventyay.common.exceptions import SubmissionError
from eventyay.common.forms.fields import SizeFileInput
from eventyay.common.session_video import (
    get_submission_video_url,
    prefetch_submission_video_urls,
    session_videos_enabled as event_session_videos_enabled,
    set_submission_video_urls,
    video_urls_from_prefetched_submission,
)
from eventyay.common.video_embed import parse_video_urls
from eventyay.common.text.phrases import phrases
from eventyay.common.views.generic import CreateOrUpdateView, OrgaCRUDView
from eventyay.common.views.mixins import (
    ActionConfirmMixin,
    ActionFromUrl,
    EventPermissionRequired,
    ImportProcessRedirectMixin,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from eventyay.consts import SizeKey
from eventyay.orga.forms.importers import SessionImportProcessForm
from eventyay.orga.forms.submission import (
    AddSpeakerForm,
    AddSpeakerInlineForm,
    AnonymiseForm,
    SubmissionForm,
    SubmissionStateChangeForm,
)
from eventyay.submission.forms import (
    ResourceForm,
    SubmissionCommentForm,
    SubmissionFilterForm,
    TagForm,
    TalkQuestionsForm,
)
from eventyay.talk_rules.agenda import is_agenda_submission_visible
from eventyay.talk_rules.person import is_only_reviewer
from eventyay.talk_rules.submission import (
    annotate_assigned,
    get_reviewer_tracks,
    limit_for_reviewers,
)
from eventyay.talk_rules.tracks import apply_track_limit, user_has_track_limits


class SubmissionViewMixin(PermissionRequired):
    def get_queryset(self):
        return Submission.objects.filter(event=self.request.event)

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            code__iexact=self.kwargs.get('code'),
        )

    def get_permission_object(self):
        return self.object

    @cached_property
    def object(self):
        return self.get_object()

    @context
    def submission(self):
        return self.object

    @context
    @cached_property
    def has_anonymised_review(self):
        return self.request.event.review_phases.filter(can_see_speaker_names=False).exists()

    @context
    @cached_property
    def is_publicly_visible(self):
        # Check if an anonymous user could see this submission's page
        return is_agenda_submission_visible(None, self.object)


class ReviewerSubmissionFilter:
    @cached_property
    def is_only_reviewer(self):
        return is_only_reviewer(self.request.user, self.request.event)

    @cached_property
    def limit_tracks(self):
        if self.is_only_reviewer:
            return get_reviewer_tracks(self.request.event, self.request.user)

    def get_queryset(self, for_review=False):
        queryset = (
            self.request.event.submissions.all()
            .select_related('submission_type', 'event', 'track')
            .prefetch_related('speakers')
        )
        if self.is_only_reviewer:
            queryset = limit_for_reviewers(queryset, self.request.event, self.request.user, self.limit_tracks)
        elif user_has_track_limits(self.request.event, self.request.user):
            queryset = apply_track_limit(queryset, self.request.event, self.request.user)
        if for_review or 'is_reviewer' in self.request.user.get_permissions_for_event(self.request.event):
            queryset = annotate_assigned(queryset, self.request.event, self.request.user)
        return queryset


class SubmissionStateChange(SubmissionViewMixin, FormView):
    form_class = SubmissionStateChangeForm
    permission_required = 'base.state_change_submission'
    template_name = 'orga/submission/state_change.html'
    TARGETS = {
        'submit': SubmissionStates.SUBMITTED,
        'accept': SubmissionStates.ACCEPTED,
        'reject': SubmissionStates.REJECTED,
        'confirm': SubmissionStates.CONFIRMED,
        'delete': SubmissionStates.DELETED,
        'withdraw': SubmissionStates.WITHDRAWN,
        'cancel': SubmissionStates.CANCELED,
    }

    @cached_property
    def _target(self) -> str:
        """Returns one of
        submit|accept|reject|confirm|delete|withdraw|cancel."""
        return self.TARGETS[self.request.resolver_match.url_name.split('.')[-1]]

    @context
    def target(self):
        return self._target

    def do(self, force=False, pending=False):
        if pending:
            self.object.pending_state = self._target
            self.object.save()
            if self.object.pending_state in SubmissionStates.accepted_states:
                # allow configureability of pending accepted/confirmed talks
                self.object.update_talk_slots()
        else:
            method = getattr(self.object, SubmissionStates.method_names[self._target])
            method(person=self.request.user, force=force, orga=True)

    @transaction.atomic
    def form_valid(self, form):
        if self._target == self.object.state and not self.object.pending_state:
            messages.info(
                self.request,
                _(
                    'Somebody else was faster than you: '
                    'this proposal was already in the state you wanted to change it to.'
                ),
            )
            return redirect(self.get_success_url())

        current = self.object.state
        pending = form.cleaned_data.get('pending')
        try:
            self.do(pending=pending)
        except SubmissionError:
            self.do(force=True, pending=pending)

        if pending:
            return redirect(self.get_success_url())

        check_mail_template = {
            (
                SubmissionStates.ACCEPTED,
                SubmissionStates.REJECTED,
            ): self.request.event.get_mail_template(MailTemplateRoles.SUBMISSION_ACCEPT),
            (
                SubmissionStates.REJECTED,
                SubmissionStates.ACCEPTED,
            ): self.request.event.get_mail_template(MailTemplateRoles.SUBMISSION_REJECT),
        }
        if template := check_mail_template.get((current, self.object.state)):
            pending_emails = self.request.event.queued_mails.filter(
                template=template,
                sent__isnull=True,
                to_users__in=self.object.speakers.all(),
            )
            if pending_emails.exists():
                messages.warning(
                    self.request,
                    _('There may be pending emails for this proposal that are now incorrect or outdated.'),
                )
        return redirect(self.get_success_url())

    def get_success_url(self):
        url = self.request.GET.get('next')
        if self.object.state == SubmissionStates.DELETED and (not url or self.object.code in url):
            return self.request.event.orga_urls.submissions
        elif url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            return url
        return self.request.event.orga_urls.submissions

    @context
    def next(self):
        return self.request.GET.get('next')


class SubmissionSpeakersDelete(SubmissionViewMixin, ActionConfirmMixin, TemplateView):
    permission_required = 'base.update_submission'

    @cached_property
    def speaker(self):
        return get_object_or_404(User, pk=self.request.GET.get('id'))

    @property
    def action_object_name(self):
        return _('{speaker} on “{title}”').format(
            speaker=self.speaker.get_display_name(), title=self.object.title
        )

    @property
    def action_back_url(self):
        return self.object.orga_urls.speakers

    @property
    def action_confirm_label(self):
        return _('Remove speaker')

    def post(self, request, *args, **kwargs):
        submission = self.object
        speaker = self.speaker
        if submission.speakers.filter(pk=speaker.pk).exists():
            submission.remove_speaker(speaker, user=request.user)
            messages.success(request, _('The speaker has been removed from the proposal.'))
        else:
            messages.warning(request, _('The speaker was not part of this proposal.'))
        return redirect(submission.orga_urls.speakers)


class SubmissionEtherpadGenerate(SubmissionViewMixin, View):
    permission_required = 'base.update_submission'

    def post(self, request, *args, **kwargs):
        submission = self.object
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

        def fail(message, status=400):
            if is_ajax:
                return JsonResponse({'error': str(message)}, status=status)
            messages.error(request, message)
            return redirect(submission.orga_urls.edit)

        if not request.event.get_feature_flag('etherpad_enabled'):
            return fail(_('Etherpad is not enabled for this event.'))

        force = request.POST.get('force') == 'true'
        try:
            url = generate_pad_for_submission(request.event, submission, force=force)
        except (EtherpadConfigurationError, EtherpadError) as exc:
            return fail(exc)

        submission.etherpad_url = url
        submission.save(update_fields=['etherpad_url'])
        submission.log_action(
            'eventyay.submission.etherpad.generate',
            person=request.user,
            orga=True,
        )
        if is_ajax:
            return JsonResponse({'url': url})
        messages.success(request, _('An Etherpad link has been generated for this session.'))
        return redirect(submission.orga_urls.edit)


class SubmissionSpeakers(ReviewerSubmissionFilter, SubmissionViewMixin, FormView):
    template_name = 'orga/submission/speakers.html'
    permission_required = 'base.orga_list_speakerprofile'
    form_class = AddSpeakerInlineForm

    @context
    @cached_property
    def speakers(self):
        submission = self.object
        speakers_qs = submission.speakers.all().prefetch_related(
            Prefetch(
                'profiles',
                queryset=SpeakerProfile.objects.filter(event=submission.event).prefetch_related('availabilities'),
                to_attr='_event_profiles',
            ),
            Prefetch(
                'answers',
                queryset=Answer.objects.filter(
                    question__event=submission.event,
                    question__is_visible_to_reviewers=True,
                    question__target=TalkQuestionTarget.SPEAKER,
                )
                .select_related('question')
                .order_by('question__position'),
                to_attr='_reviewer_answers',
            ),
            Prefetch(
                'submissions',
                queryset=Submission.objects.filter(event=submission.event),
                to_attr='_event_submissions',
            ),
        )
        return [
            {
                'user': speaker,
                'profile': speaker.event_profile(submission.event),
                'other_submissions': [s for s in speaker._event_submissions if s.code != submission.code],
                'email': speaker.email,
                'avatar': speaker.avatar,
                'avatar_url': speaker.get_avatar_url(event=submission.event),
                'avatar_source': speaker.avatar_source,
                'avatar_license': speaker.avatar_license,
                'reviewer_answers': speaker._reviewer_answers,
            }
            for speaker in speakers_qs
        ]

    def form_valid(self, form):
        if email := form.cleaned_data.get('email'):
            speaker = self.object.add_speaker(
                email=email,
                name=form.cleaned_data.get('name'),
                locale=form.cleaned_data.get('locale'),
                biography=form.cleaned_data.get('biography'),
                user=self.request.user,
            )
            messages.success(self.request, _('The speaker has been added to the proposal.'))
            return redirect(speaker.event_profile(self.request.event).orga_urls.base)
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        kwargs['require_name'] = True
        kwargs['include_biography'] = True
        return kwargs

    def get_success_url(self):
        return self.object.orga_urls.speakers


class SubmissionContent(ActionFromUrl, ReviewerSubmissionFilter, SubmissionViewMixin, CreateOrUpdateView):
    model = Submission
    form_class = SubmissionForm
    template_name = 'orga/submission/content_edit.html'

    def get_object(self):
        try:
            return super().get_object()
        except Http404 as not_found:
            if self.request.path.rstrip('/').endswith('/new'):
                return None
            return not_found

    @cached_property
    def write_permission_required(self):
        if self.kwargs.get('code'):
            return 'base.update_submission'
        return 'base.create_submission'

    @context
    def size_warning(self):
        return SizeFileInput.get_size_warning()

    @cached_property
    def _formset(self):
        formset_class = inlineformset_factory(
            Submission,
            Resource,
            form=ResourceForm,
            formset=BaseModelFormSet,
            can_delete=True,
            extra=0,
        )
        submission = self.get_object()
        return formset_class(
            self.request.POST if self.request.method == 'POST' else None,
            files=self.request.FILES if self.request.method == 'POST' else None,
            queryset=(
                submission.resources.exclude(kind=ResourceKind.SLIDES) if submission else Resource.objects.none()
            ),
            prefix='resource',
        )

    @context
    def formset(self):
        return self._formset

    @context
    @cached_property
    def new_speaker_form(self):
        if not self.get_object():
            return AddSpeakerForm(
                data=self.request.POST if self.request.method == 'POST' else None,
                event=self.request.event,
                prefix='speaker',
                include_biography=True,
                draft_save=self.request.POST.get('state') == SubmissionStates.DRAFT,
            )

    @cached_property
    def _questions_form(self):
        submission = self.get_object()
        form_kwargs = self.get_form_kwargs()
        kwargs = {
            'data': self.request.POST if self.request.method == 'POST' else None,
            'files': self.request.FILES if self.request.method == 'POST' else None,
            'target': 'submission',
            'submission': submission,
            'event': self.request.event,
            'include_session_video': False,
            'for_reviewers': (
                not self.request.user.has_perm('base.orga_update_submission', self.request.event)
                and self.request.user.has_perm('base.list_review', self.request.event)
            ),
            'readonly': form_kwargs['read_only'],
        }
        # When creating a new submission, filter out track/type specific questions
        if not submission:
            kwargs['skip_limited_questions'] = True
        return TalkQuestionsForm(**kwargs)

    @context
    def questions_form(self):
        return self._questions_form

    @context
    @cached_property
    def session_videos_enabled(self):
        return event_session_videos_enabled(self.request.event)

    @context
    @cached_property
    def session_video_urls(self):
        if not event_session_videos_enabled(self.request.event):
            return []
        submission = self.get_object()
        if not submission:
            return []
        stored = get_submission_video_url(submission)
        return [line for line in stored.splitlines() if line.strip()] if stored else []

    @context
    @cached_property
    def session_video_urls_text(self):
        return '\n'.join(self.session_video_urls)

    def _save_session_video_urls(self, submission):
        if not event_session_videos_enabled(self.request.event):
            return True
        if not self.request.user.has_perm('base.orga_update_submission', self.request.event):
            return True
        raw = self.request.POST.get('session_video_urls', '')
        urls = [line.strip() for line in raw.splitlines() if line.strip()]
        try:
            set_submission_video_urls(submission, urls)
        except ValueError as exc:
            messages.error(self.request, str(exc))
            return False
        return True

    def save_formset(self, obj):
        if not self._formset.is_valid():
            return False

        for form in self._formset.initial_forms:
            if form in self._formset.deleted_forms:
                if not form.instance.pk:
                    continue
                obj.log_action(
                    'eventyay.submission.resource.delete',
                    person=self.request.user,
                    data={'id': form.instance.pk},
                )
                form.instance.delete()
                form.instance.pk = None
            elif form.has_changed():
                form.instance.submission = obj
                form.instance.kind = ResourceKind.GENERIC
                form.save()
                change_data = {key: form.cleaned_data.get(key) for key in form.changed_data}
                change_data['id'] = form.instance.pk
                obj.log_action(
                    'eventyay.submission.resource.update',
                    person=self.request.user,
                    orga=True,
                )

        extra_forms = [
            form
            for form in self._formset.extra_forms
            if form.has_changed and not self._formset._should_delete_form(form) and form.is_valid()
        ]
        for form in extra_forms:
            form.instance.submission = obj
            form.instance.kind = ResourceKind.GENERIC
            form.save()
            obj.log_action(
                'eventyay.submission.resource.create',
                person=self.request.user,
                orga=True,
                data={'id': form.instance.pk},
            )

        return True

    def get_permission_required(self):
        if 'code' in self.kwargs:
            return ['base.orga_update_submission']
        return ['base.create_submission']

    @property
    def permission_object(self):
        return self.object or self.request.event

    def get_permission_object(self):
        return self.permission_object

    def get_success_url(self) -> str:
        return self.object.orga_urls.base

    @transaction.atomic()
    def form_valid(self, form):
        created = not self.object
        self._questions_form.submission = form.instance
        if not self._questions_form.is_valid():
            messages.error(self.request, phrases.base.error_saving_changes)
            return self.get(self.request, *self.args, **self.kwargs)
        if created and not self.new_speaker_form.is_valid():
            messages.error(self.request, phrases.base.error_saving_changes)
            return self.form_invalid(form)

        self.object = form.instance
        form.instance.event = self.request.event
        form.save()
        self._questions_form.save()
        if not self._save_session_video_urls(form.instance):
            return self.get(self.request, *self.args, **self.kwargs)

        if created:
            if email := self.new_speaker_form.cleaned_data['email']:
                form.instance.add_speaker(
                    email=email,
                    name=self.new_speaker_form.cleaned_data['name'],
                    locale=self.new_speaker_form.cleaned_data.get('locale'),
                    user=self.request.user,
                    biography=self.new_speaker_form.cleaned_data.get('biography'),
                )
        else:
            formset_result = self.save_formset(form.instance)
            if not formset_result:
                return self.get(self.request, *self.args, **self.kwargs)
            messages.success(self.request, _('The proposal has been updated!'))
        if form.has_changed():
            action = 'eventyay.submission.' + ('create' if created else 'update')
            form.instance.log_action(action, person=self.request.user, orga=True)
            self.request.event.cache.set('rebuild_schedule_export', True, None)
            if 'is_featured' in form.changed_data:
                from eventyay.agenda.views.utils import clear_schedule_caches
                clear_schedule_caches(self.request.event, submission=form.instance)
        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        instance = kwargs.get('instance')
        kwargs['anonymise'] = getattr(instance, 'pk', None) and not self.request.user.has_perm(
            'base.orga_list_speakerprofile', instance
        )
        kwargs['read_only'] = kwargs['read_only'] or kwargs['anonymise']
        return kwargs

    @context
    @cached_property
    def can_edit(self):
        return self.object and self.request.user.has_perm('base.orga_update_submission', self.request.event)


class SubmissionContentView(SubmissionContent):
    template_name = 'orga/submission/content.html'
    http_method_names = ['get', 'head', 'options']

    def get_permission_required(self):
        if 'code' in self.kwargs:
            return ['base.orga_list_submission']  # View permission for reviewers
        return ['base.create_submission']

    @context
    def available_tags_json(self):
        tags = []
        for tag in self.request.event.tags.all().order_by('tag'):
            description = tag.description
            if description is not None and not isinstance(description, str):
                description = str(description)
            tags.append(
                {
                    'id': tag.id,
                    'tag': tag.tag,
                    'color': tag.color,
                    'foreground_color': tag.foreground_color,
                    'description': description or '',
                }
            )
        return tags


class BaseSubmissionList(Sortable, ReviewerSubmissionFilter, PaginationMixin, ListView):
    model = Submission
    context_object_name = 'submissions'
    filter_fields = ()
    sortable_fields = (
        'code',
        'title',
        'state',
        'is_featured',
        'submission_type__name',
        'track__name',
    )
    usable_states = None

    def get_filter_form(self):
        return SubmissionFilterForm(
            data=self.request.GET,
            event=self.request.event,
            usable_states=self.usable_states,
            limit_tracks=self.limit_tracks,
            search_fields=self.get_default_filters(),
        )

    @context
    @cached_property
    def filter_form(self):
        return self.get_filter_form()

    def get_default_filters(self, *args, **kwargs):
        default_filters = {'code__icontains', 'title__icontains'}
        if self.request.user.has_perm('base.orga_list_speakerprofile', self.request.event):
            default_filters.add('speakers__fullname__icontains')
        return default_filters

    def _get_base_queryset(self, for_review=False):
        # If somebody has *only* reviewer permissions for this event, they can only
        # see the proposals they can review.
        qs = super().get_queryset(for_review=for_review).order_by('-id')
        if not self.filter_form.is_valid():
            return qs
        return self.filter_form.filter_queryset(qs)

    def get_queryset(self):
        return self.sort_queryset(self._get_base_queryset()).distinct()


class SubmissionList(EventPermissionRequired, BaseSubmissionList):
    template_name = 'orga/submission/list.html'
    permission_required = 'base.orga_list_submission'
    paginate_by = 25
    default_sort_field = 'state'
    secondary_sort = {'state': ('pending_state',)}

    @context
    def show_submission_types(self):
        return self.request.event.submission_types.all().count() > 1

    @context
    @cached_property
    def pending_changes(self):
        return self.get_queryset().filter(pending_state__isnull=False).count()

    @context
    def show_tracks(self):
        if self.request.event.get_feature_flag('use_tracks'):
            if self.limit_tracks:
                return len(self.limit_tracks) > 1
            return self.request.event.tracks.all().count() > 1

    @context
    def session_videos_enabled(self):
        return event_session_videos_enabled(self.request.event)

    def get_queryset(self):
        qs = super().get_queryset()
        if event_session_videos_enabled(self.request.event):
            return prefetch_submission_video_urls(qs, self.request.event)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        submissions = ctx.get('submissions') or ctx.get('object_list') or []
        enabled = event_session_videos_enabled(self.request.event)
        for submission in submissions:
            if enabled:
                urls = video_urls_from_prefetched_submission(submission)
            else:
                urls = []
            submission.session_video_urls = urls
            submission.session_video_urls_json = json.dumps(urls)
        return ctx


class FeedbackList(SubmissionViewMixin, PaginationMixin, ListView):
    template_name = 'orga/submission/feedback_list.html'
    context_object_name = 'feedback'
    paginate_by = 25
    permission_required = 'base.view_feedback_submission'

    def get_queryset(self):
        return self.submission.feedback.all().order_by('pk')

    def get_object(self):
        return get_object_or_404(
            Submission.objects.filter(event=self.request.event),
            code__iexact=self.kwargs.get('code'),
        )

    @cached_property
    def submission(self):
        return self.get_object()

    def get_permission_object(self):
        return self.submission


class ToggleFeatured(SubmissionViewMixin, View):
    permission_required = 'base.orga_update_submission'

    def get_permission_object(self):
        return self.object or self.request.event

    def post(self, *args, **kwargs):
        self.object.is_featured = not self.object.is_featured
        self.object.save(update_fields=['is_featured'])
        from eventyay.agenda.views.utils import clear_schedule_caches
        clear_schedule_caches(self.request.event, submission=self.object)
        return HttpResponse()


class SubmissionVideoLink(SubmissionViewMixin, View):
    """Create/update/clear canonical session video links from the overview table."""

    permission_required = 'base.orga_update_submission'

    def get_permission_object(self):
        return self.object or self.request.event

    def post(self, request, *args, **kwargs):
        if not event_session_videos_enabled(self.request.event):
            return JsonResponse(
                {'ok': False, 'error': gettext('Session videos are disabled for this event.')},
                status=403,
            )
        try:
            payload = json.loads(request.body.decode() or '{}')
        except json.JSONDecodeError:
            payload = request.POST
        if not hasattr(payload, 'get'):
            payload = {}
        if 'urls' in payload:
            raw_urls = payload.get('urls') or []
            if isinstance(raw_urls, str):
                urls = parse_video_urls(raw_urls)
            elif isinstance(raw_urls, list):
                urls = [str(item).strip() for item in raw_urls if str(item).strip()]
            else:
                urls = []
        else:
            urls = parse_video_urls(payload.get('url', '') or '')
        try:
            stored = set_submission_video_urls(self.object, urls)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

        from eventyay.agenda.views.utils import clear_schedule_caches

        clear_schedule_caches(self.request.event, submission=self.object)
        return JsonResponse(
            {
                'ok': True,
                'urls': stored,
                'url': '\n'.join(stored),
                'has_video': bool(stored),
            }
        )


class ApplyPending(SubmissionViewMixin, View):
    permission_required = 'base.state_change_submission'

    def post(self, request, *args, **kwargs):
        submission = self.object
        try:
            submission.apply_pending_state(person=request.user)
        except Exception:
            submission.apply_pending_state(person=request.user, force=True)
        return redirect(submission.orga_urls.base)


class Anonymise(SubmissionViewMixin, UpdateView):
    permission_required = 'base.orga_update_submission'
    template_name = 'orga/submission/anonymise.html'
    form_class = AnonymiseForm

    def get_permission_object(self):
        return self.object or self.request.event

    @context
    @cached_property
    def next_unanonymised(self):
        return self.request.event.submissions.filter(Q(anonymised_data='{}') | Q(anonymised_data__isnull=True)).first()

    def form_valid(self, form):
        if self.object.is_anonymised:
            message = _('The anonymisation has been updated.')
        else:
            message = _('This proposal is now marked as anonymised.')
        form.save()
        messages.success(self.request, message)
        if self.request.POST.get('action', 'save') == 'next' and self.next_unanonymised:
            return redirect(self.next_unanonymised.orga_urls.anonymise)
        return redirect(self.object.orga_urls.anonymise)


class SubmissionHistory(SubmissionViewMixin, ListView):
    template_name = 'orga/submission/history.html'
    permission_required = 'base.orga_update_submission'
    paginate_by = 200
    context_object_name = 'log_entries'

    @context
    @cached_property
    def submission(self):
        return get_object_or_404(
            Submission.objects.filter(event=self.request.event),
            code__iexact=self.kwargs.get('code'),
        )

    @context
    @cached_property
    def object(self):
        return self.submission

    def get_queryset(self):
        # TODO: This does not include everything regarding this submission. Missing:
        # - scheduling changes
        # - new comments
        # - new feedback
        # - emails sent to speakers (important?)
        # - reviews written and changes
        return self.submission.logged_actions().all()

    def get_permission_object(self):
        return self.request.event


class SubmissionFeed(PermissionRequired, Feed):
    permission_required = 'base.orga_list_submission'
    feed_type = feedgenerator.Atom1Feed

    def get_object(self, request, *args, **kwargs):
        return request.event

    def title(self, obj):
        return _('{name} proposal feed').format(name=obj.name)

    def link(self, obj):
        return obj.orga_urls.submissions.full()

    def feed_url(self, obj):
        return obj.orga_urls.submission_feed.full()

    def feed_guid(self, obj):
        return obj.orga_urls.submission_feed.full()

    def description(self, obj):
        return _('Updates to the {name} schedule.').format(name=obj.name)

    def items(self, obj):
        return obj.submissions.order_by('-pk')

    def item_title(self, item):
        return _('New {event} proposal: {title}').format(event=item.event.name, title=item.title)

    def item_link(self, item):
        return item.orga_urls.base.full()

    def item_pubdate(self, item):
        return item.created


class SubmissionStatsMixin:
    @context
    @cached_property
    def can_view_submission_stats(self):
        return self.request.user.has_perm('base.orga_list_submission', self.request.event)

    @context
    @cached_property
    def show_submission_types(self):
        if not self.can_view_submission_stats:
            return False
        return self.request.event.submission_types.all().count() > 1

    @context
    @cached_property
    def show_tracks(self):
        if not self.can_view_submission_stats:
            return False
        return bool(self.request.event.get_feature_flag('use_tracks'))

    @context
    def id_mapping(self):
        if not self.can_view_submission_stats:
            return '{}'
        data = {
            'type': {
                str(submission_type): submission_type.id
                for submission_type in self.request.event.submission_types.all()
            },
            'state': {str(value): key for key, value in SubmissionStates.display_values.items()},
        }
        if self.show_tracks:
            data['track'] = {str(track): track.id for track in self.request.event.tracks.all()}
        locales_dict = dict(self.request.event.named_content_locales)
        data['language'] = {locales_dict.get(code, code): code for code in self.request.event.content_locales}
        return json.dumps(data)

    @context
    def timeline_annotations(self):
        if not self.can_view_submission_stats:
            return json.dumps({'deadlines': []})
        deadlines = [
            (
                submission_type.deadline.astimezone(self.request.event.tz).strftime('%Y-%m-%d'),
                str(_('Deadline')) + f' ({submission_type.name})',
            )
            for submission_type in self.request.event.submission_types.filter(deadline__isnull=False)
        ]
        if hasattr(self.request.event, 'cfp') and self.request.event.cfp.deadline:
            deadlines.append(
                (
                    self.request.event.cfp.deadline.astimezone(self.request.event.tz).strftime('%Y-%m-%d'),
                    str(_('Deadline')),
                )
            )
        return json.dumps({'deadlines': deadlines})

    @cached_property
    def raw_submission_timeline_data(self):
        if not self.can_view_submission_stats:
            return []
        rows = (
            self.request.event.submissions
            .exclude(state=SubmissionStates.DELETED)
            .filter(created__isnull=False)
            .annotate(date=TruncDate('created', tzinfo=self.request.event.tz))
            .values('date')
            .annotate(count=DbCount('id'))
            .order_by('date')
        )
        if not rows:
            return []

        dates = {row['date']: row['count'] for row in rows if row['date']}
        if not dates:
            return []

        min_date = min(dates.keys())
        max_date = max(dates.keys())
        date_range = rrule.rrule(
            rrule.DAILY,
            count=(max_date - min_date).days + 1,
            dtstart=min_date,
        )
        return [
            {'x': date.date().isoformat(), 'y': dates.get(date.date(), 0)}
            for date in date_range
        ]

    @context
    def submission_timeline_data(self):
        if self.raw_submission_timeline_data:
            return json.dumps(self.raw_submission_timeline_data)
        return ''

    @context
    @cached_property
    def submission_state_data(self):
        if not self.can_view_submission_stats:
            return ''
        rows = (
            Submission.all_objects
            .exclude(state=SubmissionStates.DRAFT)
            .filter(event=self.request.event)
            .values('state')
            .annotate(count=DbCount('id'))
        )
        state_labels = dict(SubmissionStates.get_choices())
        counter = {str(state_labels.get(row['state'], row['state'])): row['count'] for row in rows if row['count']}
        if not counter:
            return ''
        return json.dumps(
            sorted(
                [{'label': label, 'value': value} for label, value in counter.items()],
                key=itemgetter('label'),
            )
        )

    @context
    def submission_type_data(self):
        if not self.can_view_submission_stats:
            return ''
        rows = (
            Submission.objects
            .filter(event=self.request.event)
            .values('submission_type_id')
            .annotate(count=DbCount('id'))
        )
        types_dict = {
            st.id: str(st)
            for st in self.request.event.submission_types.all()
        }
        counter = {
            types_dict[row['submission_type_id']]: row['count']
            for row in rows if row['submission_type_id'] in types_dict and row['count']
        }
        if not counter:
            return ''
        return json.dumps(
            sorted(
                [{'label': label, 'value': value} for label, value in counter.items()],
                key=itemgetter('label'),
            )
        )

    @context
    def submission_track_data(self):
        if not self.can_view_submission_stats:
            return ''
        if self.request.event.get_feature_flag('use_tracks'):
            rows = (
                Submission.objects
                .filter(event=self.request.event, track__isnull=False)
                .values('track_id')
                .annotate(count=DbCount('id'))
            )
            tracks_dict = {
                tr.id: str(tr.name)
                for tr in self.request.event.tracks.all()
            }
            counter = {
                tracks_dict[row['track_id']]: row['count']
                for row in rows if row['track_id'] in tracks_dict and row['count']
            }
            if not counter:
                return ''
            return json.dumps(
                sorted(
                    [{'label': label, 'value': value} for label, value in counter.items()],
                    key=itemgetter('label'),
                )
            )
        return ''

    @context
    def submission_language_data(self):
        if not self.can_view_submission_stats:
            return ''
        locales_dict = dict(self.request.event.named_content_locales)
        rows = (
            Submission.objects
            .filter(event=self.request.event)
            .values('content_locale')
            .annotate(count=DbCount('id'))
        )
        counter = {
            str(locales_dict.get(row['content_locale'], row['content_locale'])): row['count']
            for row in rows if row['content_locale'] and row['count']
        }
        if not counter:
            return ''
        return json.dumps(
            sorted(
                [{'label': label, 'value': value} for label, value in counter.items()],
                key=itemgetter('label'),
            )
        )

    @context
    def talk_timeline_data(self):
        if not self.can_view_submission_stats:
            return ''
        rows = (
            self.request.event.submissions
            .filter(state__in=SubmissionStates.accepted_states, created__isnull=False)
            .annotate(date=TruncDate('created', tzinfo=self.request.event.tz))
            .values('date')
            .annotate(count=DbCount('id'))
            .order_by('date')
        )
        if not rows:
            return ''

        data = {row['date'].isoformat(): row['count'] for row in rows if row['date']}
        if data:
            if self.raw_submission_timeline_data:
                return json.dumps(
                    [{'x': point['x'], 'y': data.get(point['x'][:10], 0)} for point in self.raw_submission_timeline_data]
                )
            return json.dumps([{'x': date, 'y': count} for date, count in sorted(data.items())])
        return ''

    @context
    def talk_state_data(self):
        if not self.can_view_submission_stats:
            return ''
        rows = (
            self.request.event.submissions
            .filter(state__in=SubmissionStates.accepted_states)
            .values('state')
            .annotate(count=DbCount('id'))
        )
        state_labels = dict(SubmissionStates.get_choices())
        counter = {str(state_labels.get(row['state'], row['state'])): row['count'] for row in rows if row['count']}
        if not counter:
            return ''
        return json.dumps(
            sorted(
                [{'label': label, 'value': value} for label, value in counter.items()],
                key=itemgetter('label'),
            )
        )

    @context
    def talk_type_data(self):
        if not self.can_view_submission_stats:
            return ''
        rows = (
            self.request.event.submissions
            .filter(state__in=SubmissionStates.accepted_states)
            .values('submission_type_id')
            .annotate(count=DbCount('id'))
        )
        types_dict = {
            st.id: str(st)
            for st in self.request.event.submission_types.all()
        }
        counter = {
            types_dict[row['submission_type_id']]: row['count']
            for row in rows if row['submission_type_id'] in types_dict and row['count']
        }
        if not counter:
            return ''
        return json.dumps(
            sorted(
                [{'label': label, 'value': value} for label, value in counter.items()],
                key=itemgetter('label'),
            )
        )

    @context
    def talk_track_data(self):
        if not self.can_view_submission_stats:
            return ''
        if self.request.event.get_feature_flag('use_tracks'):
            rows = (
                self.request.event.submissions
                .filter(state__in=SubmissionStates.accepted_states, track__isnull=False)
                .values('track_id')
                .annotate(count=DbCount('id'))
            )
            tracks_dict = {
                tr.id: str(tr.name)
                for tr in self.request.event.tracks.all()
            }
            counter = {
                tracks_dict[row['track_id']]: row['count']
                for row in rows if row['track_id'] in tracks_dict and row['count']
            }
            if not counter:
                return ''
            return json.dumps(
                sorted(
                    [{'label': label, 'value': value} for label, value in counter.items()],
                    key=itemgetter('label'),
                )
            )
        return ''

    @context
    def talk_language_data(self):
        if not self.can_view_submission_stats:
            return ''
        locales_dict = dict(self.request.event.named_content_locales)
        rows = (
            self.request.event.submissions
            .filter(state__in=SubmissionStates.accepted_states)
            .values('content_locale')
            .annotate(count=DbCount('id'))
        )
        counter = {
            str(locales_dict.get(row['content_locale'], row['content_locale'])): row['count']
            for row in rows if row['content_locale'] and row['count']
        }
        if not counter:
            return ''
        return json.dumps(
            sorted(
                [{'label': label, 'value': value} for label, value in counter.items()],
                key=itemgetter('label'),
            )
        )


class AllFeedbacksList(EventPermissionRequired, PaginationMixin, ListView):
    model = Feedback
    context_object_name = 'feedback'
    template_name = 'orga/submission/feedbacks_list.html'
    permission_required = 'base.orga_list_submission'
    paginate_by = 25

    def get_queryset(self):
        qs = Feedback.objects.order_by('-pk').select_related('talk', 'author').filter(talk__event=self.request.event)
        
        tab = self.request.GET.get('tab', 'published')
        if tab == 'published':
            qs = qs.filter(status='published', is_public=True)
        elif tab == 'pending':
            qs = qs.filter(status='pending', is_public=True)
        elif tab == 'hidden':
            qs = qs.filter(status='hidden', is_public=True)
        elif tab == 'anonymous':
            qs = qs.filter(is_public=False)
            
        return qs
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_tab'] = self.request.GET.get('tab', 'published')
        context['banned_user_ids'] = list(self.request.event.banned_users.values_list('id', flat=True))
        return context

class FeedbackBulkAction(EventPermissionRequired, View):
    permission_required = 'base.orga_update_submission'

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        feedback_ids = request.POST.getlist('feedback_ids')
        
        if not feedback_ids:
            messages.warning(request, _('No items selected.'))
            return redirect(request.GET.get('next', request.event.orga_urls.feedback))
            
        feedbacks = Feedback.objects.filter(pk__in=feedback_ids, talk__event=request.event)
        
        if action == 'approve':
            count = feedbacks.filter(status='pending').update(status='published')
            messages.success(request, _('Successfully approved %d feedback(s).') % count)
        elif action == 'hide':
            count = feedbacks.exclude(status='hidden').update(status='hidden')
            messages.success(request, _('Successfully hid %d feedback(s).') % count)
        elif action == 'delete':
            count = feedbacks.exclude(status='deleted').update(status='deleted')
            messages.success(request, _('Successfully deleted %d feedback(s).') % count)
            
        return redirect(request.GET.get('next', request.event.orga_urls.feedback))

class FeedbackUpdateStatus(EventPermissionRequired, View):
    permission_required = 'base.orga_update_submission'

    def get(self, request, *args, **kwargs):
        feedback = get_object_or_404(Feedback, pk=self.kwargs['pk'], talk__event=request.event)
        action = request.GET.get('action')
        if action == 'delete':
            from django.shortcuts import render
            return render(request, 'orga/submission/feedback_delete.html', {'object': feedback})
        return redirect(request.GET.get('next', request.event.orga_urls.feedback))

    def post(self, request, *args, **kwargs):
        feedback = get_object_or_404(Feedback, pk=self.kwargs['pk'], talk__event=request.event)
        action = request.POST.get('action')
        
        if action == 'approve' and feedback.status == 'pending':
            feedback.status = 'published'
            feedback.save()
            messages.success(request, _('Feedback approved.'))
        elif action == 'hide' and feedback.status != 'hidden':
            feedback.status = 'hidden'
            feedback.save()
            messages.success(request, _('Feedback hidden.'))
        elif action == 'delete':
            feedback.status = 'deleted'
            feedback.save()
            messages.success(request, _('Feedback deleted.'))
        elif action == 'ban':
            if feedback.author:
                request.event.banned_users.add(feedback.author)
                feedback.status = 'hidden'
                feedback.save()
                messages.success(request, _('User banned successfully.'))
            else:
                messages.error(request, _('Cannot ban anonymous user.'))
        elif action == 'unban':
            if feedback.author:
                request.event.banned_users.remove(feedback.author)
                messages.success(request, _('User unbanned successfully.'))
            else:
                messages.error(request, _('Cannot unban anonymous user.'))
            
        next_url = request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            return redirect(next_url)
        return redirect(request.event.orga_urls.feedback)


class TagView(OrgaCRUDView):
    model = Tag
    form_class = TagForm
    template_namespace = 'orga/submission'

    def get_queryset(self):
        return self.request.event.tags.all().order_by('tag')

    def get_generic_title(self, instance=None):
        if instance:
            return _('Tag') + f' {phrases.base.quotation_open}{instance.tag}{phrases.base.quotation_close}'
        if self.action == 'create':
            return _('New tag')
        return _('Tags')


class CommentList(SubmissionViewMixin, FormView):
    template_name = 'orga/submission/comments.html'
    permission_required = 'base.view_submissioncomment'
    write_permission_required = 'base.add_submissioncomment'
    form_class = SubmissionCommentForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['submission'] = self.object
        kwargs['user'] = self.request.user
        return kwargs

    @context
    @cached_property
    def comments(self):
        return self.object.comments.all().select_related('user').order_by('created')

    def form_valid(self, form):
        form.save()
        messages.success(self.request, phrases.base.saved)
        return redirect(self.object.orga_urls.comments)


class CommentDelete(SubmissionViewMixin, ActionConfirmMixin, TemplateView):
    permission_required = 'base.delete_submissioncomment'

    @property
    def action_back_url(self):
        return self.object.submission.orga_urls.comments

    @property
    def action_object_name(self):
        return _('Your comment on “{title}”').format(title=self.object.submission.title)

    def get_object(self):
        return get_object_or_404(
            SubmissionComment,
            submission__code__iexact=self.kwargs['code'],
            pk=self.kwargs['pk'],
        )

    def post(self, request, *args, **kwargs):
        comment = self.get_object()
        comment.submission.log_action('eventyay.submission.comment.delete', person=request.user, orga=True)
        comment.delete()
        messages.success(request, _('The comment has been deleted.'))
        return redirect(comment.submission.orga_urls.comments)


class ApplyPendingBulk(EventPermissionRequired, BaseSubmissionList):
    permission_required = 'base.state_change_submission'
    template_name = 'orga/submission/apply_pending.html'

    @cached_property
    def submissions(self):
        return self.get_queryset().filter(pending_state__isnull=False)

    @context
    @cached_property
    def submission_count(self):
        return len(self.submissions)

    def post(self, request, *args, **kwargs):
        for submission in self.submissions:
            try:
                submission.apply_pending_state(person=self.request.user)
            except Exception:
                submission.apply_pending_state(person=self.request.user, force=True)
        messages.success(
            self.request,
            str(_('Changed {count} proposal states.')).format(count=self.submission_count),
        )
        url = self.request.GET.get('next')
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            return redirect(url)
        return redirect(self.request.event.orga_urls.submissions)

    @context
    def next(self):
        return self.request.GET.get('next')


class SubmissionImportProcessView(ImportProcessRedirectMixin, EventPermissionRequired, AsyncAction, FormView):
    permission_required = 'base.update_event'
    template_name = 'orga/submission/import_process.html'
    form_class = SessionImportProcessForm
    task = import_submissions
    known_errortypes = ['ImportExecutionError']
    IMPORT_FILENAME = 'session_import.csv'

    import_process_url_name = 'settings.import_export.submissions_import_process'
    import_page_url_name = 'import_export_settings'
    import_target = 'session'

    @cached_property
    def import_settings_url(self):
        base = self.request.event.orga_urls.import_export_settings
        query = urlencode({'import_target': self.import_target})
        return f'{base}?{query}#tab-import'

    def dispatch(self, request, *args, **kwargs):
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return super().dispatch(request, *args, **kwargs)
        try:
            _ = self.file
        except Http404:
            messages.error(request, _('The uploaded CSV file is missing or expired. Please upload it again.'))
            return redirect(self.import_settings_url)
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def file(self):
        return get_object_or_404(
            CachedFile,
            pk=self.kwargs.get('file'),
            filename=self.IMPORT_FILENAME,
            session_key=self.request.session.session_key,
        )

    @cached_property
    def parsed(self):
        return parse_csv(self.file.file, settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_CSV])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['headers'] = self.parsed.fieldnames if self.parsed else []
        kwargs['event'] = self.request.event
        kwargs['initial'] = self.request.event.settings.submission_import_settings
        return kwargs

    @context
    def preview_rows(self):
        if not self.parsed:
            return []
        rows = []
        headers = self.parsed.fieldnames or []
        for i, row in enumerate(self.parsed):
            if i >= 5:
                break
            rows.append([row.get(h, '') for h in headers])
        return rows

    @context
    def headers(self):
        return self.parsed.fieldnames if self.parsed else []

    def get(self, request, *args, **kwargs):
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return self.get_result(request)
        if not self.parsed:
            messages.error(request, _('Could not parse the uploaded CSV file.'))
            return redirect(self.import_settings_url)
        return FormView.get(self, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not self.parsed:
            messages.error(request, _('Could not parse the uploaded CSV file.'))
            return redirect(self.import_settings_url)
        return FormView.post(self, request, *args, **kwargs)

    def form_valid(self, form):
        self.request.event.settings.submission_import_settings = form.cleaned_data
        return self.do(
            self.request.event.pk,
            str(self.file.id),
            form.cleaned_data,
            self.request.LANGUAGE_CODE,
            self.request.user.pk,
        )

    def get_success_url(self, value):
        return self.import_settings_url

    def get_error_url(self):
        return self.import_settings_url

    def get_success_message(self, value):
        if isinstance(value, dict):
            msg = _('Session import complete: {created} created, {updated} updated, {skipped} skipped.').format(
                created=value.get('created', 0),
                updated=value.get('updated', 0),
                skipped=value.get('skipped', 0),
            )
            errors = value.get('errors', [])
            if errors:
                msg += ' ' + _('Errors: {errors}').format(errors='; '.join(str(e) for e in errors[:10]))
            return msg
        return _('The session import was successful.')
