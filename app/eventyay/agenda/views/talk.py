import datetime as dt
import logging
from enum import StrEnum
from http import HTTPStatus
from typing import TypeVar
from urllib.parse import unquote, urljoin, urlparse

import jwt
import vobject
from django.conf import settings
from django.contrib import messages
from django.db.models import F, Q
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView, View
from django_context_decorator import context
from django_scopes import scope
from i18nfield.utils import I18nJSONEncoder

from eventyay.agenda.export_resources import public_resource_attachments, public_resource_links
from eventyay.agenda.signals import register_recording_provider
from eventyay.agenda.feedback_access import (
    TicketCheckResult,
    feedback_is_public_for_submission,
    feedback_period_open,
    get_feedback_anonymous_mode,
    user_can_give_feedback,
    user_has_event_ticket,
)
from eventyay.agenda.views.utils import (
    WipAgendaPreviewPageMixin,
    build_enriched_schedule_json,
    build_google_calendar_url,
    build_talk_schedule_json,
    encode_email,
    is_email_like,
)
from eventyay.base.models import (
    Event,
    Feedback,
    Submission,
    SubmissionFavourite,
    SubmissionStates,
    TalkQuestionVariant,
    TalkSlot,
    User,
)
from eventyay.cfp.views.event import EventPageMixin
from eventyay.common.text.phrases import phrases
from eventyay.common.urls import get_base_url
from eventyay.common.utils.language import localize_event_text
from eventyay.common.video_embed import get_video_embed_info, parse_video_urls
from eventyay.common.views.helpers import login_redirect_with_next, redirect_or_json_redirect
from eventyay.common.views.mixins import (
    EventPermissionRequired,
    PermissionRequired,
    SocialMediaCardMixin,
)
from eventyay.submission.forms import FeedbackForm
from eventyay.talk_rules.agenda import agenda_schedule_for_user, filter_agenda_slots
from eventyay.orga.utils.colors import get_contrast_color


logger = logging.getLogger(__name__)


class VideoJoinError(StrEnum):
    # The string value looks diffrent from the enum name
    # because other code may depend on this string value.
    NOT_ALLOWED = 'user_not_allowed'
    MISCONFIGURED = 'missing_configuration'


class TalkMixin(PermissionRequired):
    permission_required = 'base.view_public_submission'
    wip_preview = False

    def get_queryset(self):
        return self.request.event.submissions.prefetch_related(
            'slots',
            'resources',
        ).select_related('submission_type', 'track', 'event', 'event__organizer')

    @cached_property
    def object(self):
        return get_object_or_404(
            self.get_queryset(),
            code__iexact=self.kwargs['slug'],
        )

    @context
    @cached_property
    def submission(self):
        return self.object

    def get_permission_object(self):
        return self.submission

    def agenda_schedule(self):
        return agenda_schedule_for_user(
            self.request.event,
            self.request.user,
            wip_preview=self.wip_preview,
        )

    def filter_visible_slots(self, qs):
        return filter_agenda_slots(
            qs,
            self.request.user,
            self.request.event,
            wip_preview=self.wip_preview,
        )


def talk_starrers(request, event, slug, **kwargs):
    """Return starrer information for a session.

    This endpoint is intended for the schedule web component and is safe for
    public use. It exposes identifying information only for users who are
    public, non-deleted, have a non-email-like display name, and a non-empty
    code. Other favourites are returned as anonymous placeholders.
    """

    if not request.event.get_feature_flag('session_popularity_enabled'):
        response = JsonResponse({'total': 0, 'public_total': 0, 'items': []})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'authorization,content-type'
        return response

    submission = request.event.submissions.filter(code__iexact=slug).select_related('event', 'event__organizer').first()
    if not submission or not request.user.has_perm('base.view_public_submission', submission):
        raise Http404()

    try:
        limit = int(request.GET.get('limit', 15))
    except (TypeError, ValueError):
        limit = 15

    # ``limit=0`` means "return everything" (within a reasonable ceiling).
    max_limit = 1000
    if limit < 0:
        limit = 15
    if limit == 0:
        limit = max_limit
    limit = min(limit, max_limit)

    with scope(event=request.event):
        qs = SubmissionFavourite.objects.filter(submission=submission)
        total = qs.count()
        public_total = qs.filter(user__show_publicly=True, user__deleted=False).count()

        base_url = str(request.event.urls.base)
        items = []
        for fav in qs.select_related('user').order_by('-id')[:limit]:
            user = fav.user
            display_name = user.get_display_name() if user else ''
            is_public_user = bool(
                user and user.show_publicly and not user.deleted and user.code and not is_email_like(display_name)
            )
            if is_public_user:
                items.append(
                    {
                        'code': user.code,
                        'name': display_name,
                        'avatar_url': user.get_avatar_url(
                            event=request.event,
                            thumbnail='tiny',
                        ),
                        'url': f'{base_url}people/{user.code}/stars/',
                    }
                )
            else:
                items.append(
                    {
                        'code': f'anon-{fav.id}',
                        'name': '',
                        'avatar_url': '',
                        'url': '',
                    }
                )

    response = JsonResponse({'total': total, 'public_total': public_total, 'items': items})
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = 'authorization,content-type'
    return response


class TalkView(TalkMixin, TemplateView):
    template_name = 'agenda/talk.html'

    @context
    def schedule_json(self):
        return build_talk_schedule_json(self.request, self.submission.code)

    @context
    def schedule_version(self):
        return ''


    @cached_property
    def recording(self):
        for __, response in register_recording_provider.send_robust(self.request.event):
            if response and not isinstance(response, Exception) and getattr(response, 'get_recording', None):
                recording = response.get_recording(self.submission)
                if recording and recording['iframe']:
                    return recording
        return {}

    @context
    def recording_iframe(self):
        return self.recording.get('iframe')

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        frame_src = []
        recording_csp = self.recording.get('csp_header')
        if recording_csp:
            # Providers may return whitespace-separated CSP sources.
            frame_src.extend(part for part in str(recording_csp).split() if part)
        for answer in self.answers:
            if answer.question.variant != TalkQuestionVariant.VIDEO:
                continue
            for url in parse_video_urls(answer.answer):
                embed = get_video_embed_info(url)
                if embed:
                    frame_src.extend(embed['csp_origins'])
        # Deduplicate while preserving order
        seen = set()
        unique_frame_src = []
        for origin in frame_src:
            if origin not in seen:
                seen.add(origin)
                unique_frame_src.append(origin)
        if unique_frame_src:
            response._csp_update = {'frame-src': unique_frame_src}
        return response

    def _build_speakers_context(self, speakers_qs):
        """Enrich a speaker queryset and return a list ready for template context."""
        result = []
        for speaker in speakers_qs:
            speaker.talk_profile = speaker.event_profile(event=self.request.event)
            result.append(speaker)
        return result

    def get_context_data(self, **kwargs):
        from django.db.models import Prefetch

        ctx = super().get_context_data(**kwargs)
        schedule = self.agenda_schedule()
        if not self.request.user.has_perm('base.view_schedule', schedule):
            return ctx
        qs = schedule.talks.filter(room__isnull=False).select_related('room') if schedule else TalkSlot.objects.none()
        ctx['talk_slots'] = qs.filter(submission=self.submission).order_by('start').select_related('room')
        ctx['submission_tags'] = self.submission.tags.all()
        for tag_item in ctx['submission_tags']:
            tag_item.contrast_color = get_contrast_color(tag_item.color)
        other_slots = (
            self.filter_visible_slots(
                schedule.talks.exclude(submission_id=self.submission.pk)
            )
            if schedule
            else TalkSlot.objects.none()
        )
        other_submissions = self.request.event.submissions.filter(slots__in=other_slots).select_related(
            'event', 'event__organizer'
        )
        speakers = (
            self.submission.speakers.all()
            .with_profiles(self.request.event)
            .prefetch_related(
                Prefetch(
                    'submissions',
                    queryset=other_submissions,
                    to_attr='other_submissions',
                )
            )
        )
        ctx['speakers'] = self._build_speakers_context(speakers)
        
        # Add public feedback and form to context
        if self.request.event.get_feature_flag('use_feedback'):
            from django.db.models import Count, Q
            
            if self.request.event.get_feature_flag('feedback_show_public'):
                all_published = Feedback.objects.filter(
                    is_public=True, status='published', talk=self.submission
                ).select_related('author', 'speaker').annotate(
                    upvote_count=Count('reactions', filter=Q(reactions__is_upvote=True)),
                    downvote_count=Count('reactions', filter=Q(reactions__is_upvote=False))
                ).order_by('-created')
                
                feedback_dict = {fb.id: fb for fb in all_published}
                top_level_feedback = []
                
                user_reactions = {}
                if self.request.user.is_authenticated:
                    from eventyay.base.models.feedback import FeedbackReaction
                    reactions = FeedbackReaction.objects.filter(
                        user=self.request.user,
                        feedback__in=all_published
                    )
                    user_reactions = {r.feedback_id: r.is_upvote for r in reactions}

                for fb in all_published:
                    fb.cached_replies = []
                    fb.user_vote = user_reactions.get(fb.id)
                    
                for fb in all_published:
                    if fb.parent_id:
                        parent = feedback_dict.get(fb.parent_id)
                        if parent:
                            parent.cached_replies.append(fb)
                    else:
                        top_level_feedback.append(fb)
                
                # Sort replies chronologically (oldest first)
                for fb in top_level_feedback:
                    fb.cached_replies.sort(key=lambda x: x.created)

                ctx['public_feedback'] = top_level_feedback
            else:
                ctx['public_feedback'] = []
            if self.request.user.is_authenticated and user_can_give_feedback(
                self.request.user, self.submission
            ):
                from eventyay.submission.forms import FeedbackForm
                ctx['feedback_form'] = FeedbackForm(talk=self.submission)
            else:
                ctx['feedback_form'] = None
            ctx['can_give_feedback'] = (
                self.request.user.is_authenticated
                and user_can_give_feedback(self.request.user, self.submission)
            )
            ctx['can_moderate_feedback'] = (
                self.request.user.is_authenticated
                and self.request.user.has_perm('base.orga_update_submission', self.submission)
            )
            if ctx['can_moderate_feedback']:
                ctx['banned_user_ids'] = list(self.request.event.banned_users.values_list('id', flat=True))
            else:
                ctx['banned_user_ids'] = []
                
            ctx['feedback_period_open'] = feedback_period_open(self.submission)
            ctx['feedback_anonymous_mode'] = get_feedback_anonymous_mode(self.request.event)
                 
                
        return ctx

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponse(status=HTTPStatus.FORBIDDEN)
        if not user_can_give_feedback(request.user, self.submission):
            messages.error(request, _('You cannot leave feedback on this session.'))
            return HttpResponseRedirect(self.submission.urls.public)

        from eventyay.submission.forms import FeedbackForm
        form = FeedbackForm(talk=self.submission, data=request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.author = request.user
            feedback.is_public = feedback_is_public_for_submission(
                self.request.event,
                form.cleaned_data.get('is_public'),
            )
            if feedback.is_public and self.request.event.get_feature_flag('feedback_require_review'):
                feedback.status = 'pending'
            feedback.save()
            messages.success(self.request, _('Your feedback has been submitted.'))
            return HttpResponseRedirect(self.submission.urls.public)
            
        # On error, render the page again with the form
        ctx = self.get_context_data(**kwargs)
        ctx['feedback_form'] = form
        return self.render_to_response(ctx)

    @context
    @cached_property
    def submission_description(self):
        abstract = self.submission.abstract if self.request.event.cfp.public_abstract else ''
        description = self.submission.description if self.request.event.cfp.public_description else ''
        return (
            abstract
            or description
            or _('The session “{title}” at {event}').format(
                title=localize_event_text(self.submission.title),
                event=localize_event_text(self.request.event.name),
            )
        )

    @context
    @cached_property
    def answers(self):
        return self.submission.public_answers


class WipTalkView(WipAgendaPreviewPageMixin, TalkView):
    def has_permission(self):
        wip = self.request.event.wip_schedule
        if not wip:
            return False
        return self.submission.slots.filter(schedule=wip).exists()

    @context
    def schedule_json(self):
        return build_enriched_schedule_json(self.request, wip_preview=True)


class TalkReviewView(TalkView):
    template_name = 'agenda/talk_review.html'

    def has_permission(self):
        return self.request.event.get_feature_flag('submission_public_review')

    @cached_property
    def object(self):
        return get_object_or_404(
            Submission.all_objects.filter(event=self.request.event),
            review_code=self.kwargs['slug'],
            state__in=[
                SubmissionStates.SUBMITTED,
                SubmissionStates.DRAFT,
                SubmissionStates.ACCEPTED,
                SubmissionStates.CONFIRMED,
            ],
        )

    @context
    def hide_visibility_warning(self):
        return True

    @context
    def hide_speaker_links(self):
        return True

    def _build_speakers_context(self, speakers_qs):
        # Override to avoid calling event_profile(), which can create and save a
        # SpeakerProfile row when one doesn't exist.  That is an unwanted DB
        # write on every anonymous GET of a public review link.  Instead, use
        # the _event_profiles attribute populated by with_profiles() directly.
        result = []
        for speaker in speakers_qs:
            profiles = getattr(speaker, '_event_profiles', [])
            speaker.talk_profile = profiles[0] if profiles else None
            result.append(speaker)
        return result

    def get_context_data(self, **kwargs):
        # TalkView.get_context_data returns early (skipping speakers) when the
        # visitor lacks base.view_schedule permission – which is always the case
        # for anonymous reviewers when the schedule is not yet public.  Fill in
        # the speaker data unconditionally for the review page.
        ctx = super().get_context_data(**kwargs)
        if 'speakers' not in ctx:
            speakers = self.submission.speakers.all().with_profiles(self.request.event)
            ctx['speakers'] = self._build_speakers_context(speakers)
            ctx['submission_tags'] = self.submission.tags.all()
        return ctx


class SingleICalView(EventPageMixin, TalkMixin, View):
    def get(self, request, event, **kwargs):
        code = self.submission.code
        schedule = self.agenda_schedule()
        talk_slots = (
            self.filter_visible_slots(self.submission.slots.filter(schedule=schedule))
            if schedule
            else self.submission.slots.none()
        )

        netloc = urlparse(settings.SITE_URL).netloc
        cal = vobject.iCalendar()
        cal.add('prodid').value = f'-//eventyay//{netloc}//{code}'
        for talk in talk_slots:
            talk.build_ical(cal)
        return HttpResponse(
            cal.serialize(),
            content_type='text/calendar',
            headers={'Content-Disposition': f'attachment; filename="{request.event.slug}-{code}.ics"'},
        )


class SingleExportView(EventPageMixin, TalkMixin, View):
    """Export a single talk in iCal, JSON, XML or XCal format."""

    permission_required = 'base.list_schedule'

    def get(self, request, event, slug, **kwargs):
        fmt = kwargs.get('format', '')
        schedule = self.agenda_schedule()
        if not schedule:
            raise Http404
        talk_slots = (
            self.filter_visible_slots(self.submission.slots.filter(schedule=schedule))
            .select_related('room', 'submission', 'submission__track', 'submission__submission_type')
            .prefetch_related('submission__speakers', 'submission__resources')
        )
        if not talk_slots.exists():
            raise Http404

        handler = {
            'ics': self._render_ical,
            'json': self._render_json,
            'xml': self._render_xml,
            'xcal': self._render_xcal,
        }.get(fmt)
        if not handler:
            raise Http404
        return handler(request, talk_slots)

    def _render_ical(self, request, talk_slots):
        code = self.submission.code
        netloc = urlparse(settings.SITE_URL).netloc
        cal = vobject.iCalendar()
        cal.add('prodid').value = f'-//eventyay//{netloc}//{code}'
        for slot in talk_slots:
            slot.build_ical(cal)
        return HttpResponse(
            cal.serialize(),
            content_type='text/calendar',
            headers={'Content-Disposition': f'attachment; filename="{request.event.slug}-{code}.ics"'},
        )

    def _render_json(self, request, talk_slots):
        event = request.event
        base_url = get_base_url(event)
        show_abstract = event.cfp.public_abstract
        show_description = event.cfp.public_description
        show_biography = event.cfp.public_biography
        talks_data = []
        for slot in talk_slots:
            sub = slot.submission
            talks_data.append(
                {
                    'guid': slot.uuid,
                    'code': sub.code,
                    'id': sub.id,
                    'date': slot.local_start.isoformat(),
                    'start': slot.local_start.strftime('%H:%M'),
                    'duration': slot.export_duration,
                    'room': localize_event_text(slot.room.name) if slot.room else None,
                    'slug': slot.frab_slug,
                    'url': sub.urls.public.full(),
                    'title': localize_event_text(sub.title),
                    'track': localize_event_text(sub.track.name) if sub.track else None,
                    'type': localize_event_text(sub.submission_type.name),
                    'language': sub.content_locale,
                    'abstract': localize_event_text(sub.abstract) if show_abstract else '',
                    'description': localize_event_text(sub.description) if show_description else '',
                    'do_not_record': sub.do_not_record,
                    'persons': [
                        {
                            'code': p.code,
                            'name': p.get_display_name(),
                            'biography': localize_event_text(p.event_profile(event).biography)
                            if show_biography
                            else '',
                        }
                        for p in sub.speakers.all()
                    ],
                    'links': public_resource_links(sub, event),
                    'attachments': public_resource_attachments(sub, event),
                }
            )
        data = {
            'code': self.submission.code,
            'base_url': base_url,
            'talks': talks_data,
        }
        return JsonResponse(data, encoder=I18nJSONEncoder)

    def _render_xml(self, request, talk_slots):
        event = request.event
        base_url = get_base_url(event)
        context = {
            'talk_slots': talk_slots,
            'event': event,
            'base_url': base_url,
        }
        content = get_template('agenda/single_talk.xml').render(context=context)
        return HttpResponse(content, content_type='text/xml')

    def _render_xcal(self, request, talk_slots):
        url = get_base_url(request.event)
        domain = urlparse(url).netloc
        context = {
            'talk_slots': talk_slots,
            'url': url,
            'domain': domain,
        }
        content = get_template('agenda/single_talk.xcal').render(context=context)
        return HttpResponse(content, content_type='text/xml')


class SingleCalendarRedirectView(EventPageMixin, TalkMixin, View):
    """Redirect to Google Calendar or Webcal for a single talk."""

    permission_required = 'base.list_schedule'

    def get(self, request, event, slug, **kwargs):
        provider = kwargs.get('provider', '')
        schedule = self.agenda_schedule()
        if not schedule:
            raise Http404
        talk_slots = self.filter_visible_slots(self.submission.slots.filter(schedule=schedule))
        if not talk_slots.exists():
            raise Http404

        slot = talk_slots.first()
        parsed_base = urlparse(get_base_url(request.event))
        base_url = f'{parsed_base.scheme}://{parsed_base.netloc}'
        ical_url = urljoin(
            base_url,
            reverse(
                'agenda:ical',
                kwargs={
                    'organizer': request.event.organizer.slug,
                    'event': event,
                    'slug': slug,
                },
            ),
        )

        if provider == 'google-calendar':
            return self._google_calendar_redirect(slot, request)
        if provider == 'webcal':
            webcal_url = ical_url.replace('https://', 'webcal://').replace('http://', 'webcal://')
            response = HttpResponse(status=302)
            response['Location'] = webcal_url
            return response
        raise Http404

    def _google_calendar_redirect(self, slot, request):
        sub = slot.submission
        start = slot.start
        end = slot.real_end
        if not start or not end:
            raise Http404
        start_utc = start.astimezone(dt.UTC)
        end_utc = end.astimezone(dt.UTC)
        fmt = '%Y%m%dT%H%M%SZ'
        dates = f'{start_utc.strftime(fmt)}/{end_utc.strftime(fmt)}'
        title = localize_event_text(sub.title)
        location = localize_event_text(slot.room.name) if slot.room else ''
        details = localize_event_text(sub.abstract) if request.event.cfp.public_abstract else ''
        url = build_google_calendar_url(title, dates, location, details)
        return HttpResponseRedirect(url)


class FeedbackView(TalkMixin, FormView):
    form_class = FeedbackForm
    permission_required = 'base.view_feedback_page_submission'

    def get_queryset(self):
        return self.request.event.submissions.prefetch_related(
            'slots',
            'feedback',
            'speakers',
        ).select_related('submission_type')

    @context
    @cached_property
    def talk(self):
        return self.submission

    @context
    @cached_property
    def can_give_feedback(self):
        return self.request.user.has_perm('base.give_feedback_submission', self.talk)

    @context
    @cached_property
    def speakers(self):
        return self.talk.speakers.all()

    @cached_property
    def is_speaker(self):
        return self.request.user in self.speakers

    @cached_property
    def template_name(self):
        if self.is_speaker:
            return 'agenda/feedback.html'
        return 'agenda/feedback_form.html'

    @context
    @cached_property
    def feedback(self):
        if not self.is_speaker:
            return
        return self.talk.feedback.filter(Q(speaker=self.request.user) | Q(speaker__isnull=True)).select_related(
            'speaker'
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['talk'] = self.talk
        return kwargs

    def form_valid(self, form):
        if not self.can_give_feedback:
            return super().form_invalid(form)
        result = super().form_valid(form)
        form.save()
        messages.success(self.request, phrases.agenda.feedback_success)
        return result

    def get_success_url(self):
        return self.submission.urls.public


class TalkSocialMediaCard(SocialMediaCardMixin, TalkView):
    def get_image(self):
        return self.submission.image if self.request.event.cfp.public_image else None


class OnlineVideoJoin(EventPermissionRequired, View):
    permission_required = 'base.view_schedule'

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            # After login, return here so the user continues into the live event.
            return login_redirect_with_next(request)

        event = request.event
        logger.info('Checking video settings for event %s', event)
        required_fields = [
            ('venueless_url', 'event.settings.venueless_url'),
            ('venueless_secret', 'event.settings.venueless_secret'),
            ('venueless_issuer', 'event.settings.venueless_issuer'),
            ('venueless_audience', 'event.settings.venueless_audience'),
        ]
        for attr, label in required_fields:
            if not getattr(event.settings, attr):
                logger.info('%s is missing.', label)
                return HttpResponse(status=HTTPStatus.FORBIDDEN, content=VideoJoinError.MISCONFIGURED)

        # If the logged-in user does not have "orga.view_schedule" permission, we check
        # if he/she owns a ticket.
        if not request.user.has_perm('agenda.view_schedule', event):
            res = user_has_event_ticket(request.user, event)
            if res == TicketCheckResult.NO_TICKET:
                return HttpResponse(status=HTTPStatus.FORBIDDEN, content=VideoJoinError.NOT_ALLOWED)
            if res == TicketCheckResult.MISCONFIGURED:
                return HttpResponse(status=HTTPStatus.FORBIDDEN, content=VideoJoinError.MISCONFIGURED)

        # Redirect user to online event
        iat = dt.datetime.now(dt.UTC)
        exp = iat + dt.timedelta(days=30)
        profile = {
            'display_name': request.user.fullname,
            'fields': {
                'pretalx_id': request.user.code,
            },
        }
        if request.user.avatar_url:
            profile['profile_picture'] = request.user.get_avatar_url(request.event)

        payload = {
            'iss': event.settings.venueless_issuer,
            'aud': event.settings.venueless_audience,
            'exp': exp,
            'iat': iat,
            'uid': encode_email(request.user.email),
            'profile': profile,
            'traits': list(
                {
                    'attendee',
                    f'eventyay-video-event-{request.event.slug}',
                }
            ),
        }
        token = jwt.encode(payload, event.settings.venueless_secret, algorithm='HS256')
        redirect_url = urljoin(event.settings.venueless_url, f'#token={token}')
        logger.info('Redirect URL to Video: %s', redirect_url)
        return redirect_or_json_redirect(request, redirect_url)


_T = TypeVar('_T', str, None)


# We use TypeVar because the 2nd and 3rd items must be both `str` or both `None` at the same time.
# The annotation `tuple[str, str | None, str | None]` doesn't satisfy this requirement.
def extract_event_info_from_url(url: str) -> tuple[str, _T, _T]:
    parsed_url = urlparse(url)
    path = parsed_url.path
    parts = path.strip('/').split('/')
    if len(parts) >= 2:
        organizer, event = parts[-2:]
        return None, unquote(organizer), unquote(event)
    return None, None, None


class TalkFeedbackReactView(TalkMixin, View):
    permission_required = 'base.view_public_submission'

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=HTTPStatus.UNAUTHORIZED)

        feedback_id = kwargs.get('feedback_id')
        feedback = get_object_or_404(
            self.submission.feedback.filter(is_public=True, status='published'),
            id=feedback_id,
        )

        action = request.POST.get('action')
        if action not in ('upvote', 'downvote', 'remove'):
            return JsonResponse({'error': 'Invalid action'}, status=HTTPStatus.BAD_REQUEST)

        from eventyay.base.models import FeedbackReaction
        if action == 'remove':
            FeedbackReaction.objects.filter(feedback=feedback, user=request.user).delete()
        else:
            is_upvote = (action == 'upvote')
            FeedbackReaction.objects.update_or_create(
                feedback=feedback,
                user=request.user,
                defaults={'is_upvote': is_upvote}
            )

        upvotes = FeedbackReaction.objects.filter(feedback=feedback, is_upvote=True).count()
        downvotes = FeedbackReaction.objects.filter(feedback=feedback, is_upvote=False).count()
        return JsonResponse({'upvotes': upvotes, 'downvotes': downvotes})


class TalkFeedbackPublicActionView(TalkMixin, View):
    permission_required = 'base.view_public_submission'

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponse(status=HTTPStatus.UNAUTHORIZED)

        feedback_id = kwargs.get('feedback_id')
        action = request.POST.get('action')
        can_moderate = request.user.has_perm('base.orga_update_submission', self.submission)

        if action == 'report':
            feedback = get_object_or_404(
                self.submission.feedback.filter(is_public=True, status='published'),
                id=feedback_id,
            )
        elif can_moderate:
            feedback = get_object_or_404(self.submission.feedback, id=feedback_id)
        else:
            feedback = get_object_or_404(
                self.submission.feedback.filter(author=request.user),
                id=feedback_id,
            )

        if action == 'report':
            from django.db.models.functions import Coalesce
            Feedback.objects.filter(pk=feedback.pk).update(
                is_reported=True,
                report_count=Coalesce(F('report_count'), 0) + 1,
            )
            messages.success(request, _('Feedback reported successfully.'))
        else:
            if action == 'delete' and (feedback.author == request.user or can_moderate):
                feedback.status = 'deleted'
                feedback.save(update_fields=['status'])
                messages.success(request, _('Feedback deleted successfully.'))
            elif action == 'delete':
                messages.error(request, _('You do not have permission to delete this feedback.'))
            elif not can_moderate:
                messages.error(request, _('You do not have permission to perform this action.'))
            elif action == 'hide':
                feedback.status = 'hidden'
                feedback.save(update_fields=['status'])
                messages.success(request, _('Feedback hidden successfully.'))
            elif action == 'ban':
                if feedback.author:
                    request.event.banned_users.add(feedback.author)
                    feedback.status = 'hidden'
                    feedback.save(update_fields=['status'])
                    messages.success(request, _('User banned successfully.'))
                else:
                    messages.error(request, _('Cannot ban an anonymous user.'))
            elif action == 'unban':
                if feedback.author:
                    request.event.banned_users.remove(feedback.author)
                    messages.success(request, _('User unbanned successfully.'))
                else:
                    messages.error(request, _('Cannot unban an anonymous user.'))
            else:
                messages.error(request, _('Invalid action.'))

        return HttpResponseRedirect(self.submission.urls.public + '#feedback')
