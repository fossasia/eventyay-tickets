import json
from contextlib import suppress

from django.conf import settings
from django.db.models import Exists, OuterRef, Q
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy as _n
from django_scopes import scopes_disabled

from pretalx.event.models import Organiser
from pretalx.person.models import SpeakerProfile, User
from pretalx.submission.models import Submission


def serialize_user(user):
    base_path = settings.BASE_PATH
    return {
        "type": "user",
        "name": str(user),
        "url": base_path + "/orga/me",
    }


def serialize_orga(orga):
    return {
        "type": "organiser",
        "name": str(orga.name),
        "url": orga.orga_urls.base,
    }


def serialize_event(event):
    return {
        "type": "event",
        "name": str(event.name),
        "url": event.orga_urls.base,
        "organiser": str(event.organiser.name),
        "date_range": event.get_date_range_display(),
    }


def serialize_submission(submission):
    return {
        "type": "submission",
        "name": _n("Session", "Sessions", 1) + f" {submission.title}",
        "url": submission.orga_urls.base,
        "event": str(submission.event.name),
    }


def serialize_speaker(speaker):
    return {
        "type": "speaker",
        "name": _n("Speaker", "Speakers", 1) + f" {speaker.user.name}",
        "url": speaker.orga_urls.base,
        "event": str(speaker.event.name),
    }


def serialize_admin_user(user):
    return {
        "type": "user.admin",
        "name": _("User") + f" {user.get_display_name()}",
        "email": user.email,
        "url": user.orga_urls.admin,
    }


@scopes_disabled()
def nav_typeahead(request):
    organiser = request.GET.get("organiser")
    query = json.dumps(str(request.GET.get("query", "")))[1:-1]
    page = 1
    with suppress(ValueError):
        page = int(request.GET.get("page", "1"))

    qs_events = (
        request.user.get_events_with_any_permission()
        .filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
            | Q(organiser__name__icontains=query)
            | Q(organiser__slug__icontains=query)
        )
        .order_by("-date_from")
    )

    show_user = (
        not query
        or (request.user.email and query.lower() in request.user.email.lower())
        or (request.user.name and query.lower() in request.user.name.lower())
    )

    qs_orga = Organiser.objects.filter(
        pk__in=request.user.teams.values_list("organiser", flat=True)
    )
    if query:
        if organiser and show_user:
            qs_orga = qs_orga.filter(
                Q(name__icontains=query) | Q(slug__icontains=query) | Q(pk=organiser)
            )
        else:
            qs_orga = qs_orga.filter(
                Q(name__icontains=query) | Q(slug__icontains=query)
            )

    if organiser:
        organiser = qs_orga.filter(pk=organiser).first()

    qs_submissions = Submission.objects.none()
    qs_speakers = SpeakerProfile.objects.none()
    if query and len(query) >= 3:
        full_events = request.user.get_events_for_permission(
            can_change_submissions=True
        )
        # We'll exclude review events entirely for now, as they have extra challenges:
        # users may be restricted from seeing speaker names by review settings, or
        # limited to seeing submissions in specific tracks.
        if full_events:
            qs_submissions = Submission.objects.filter(
                Q(title__icontains=query) | Q(code__istartswith=query),
                event__in=full_events,
            ).order_by()

            qs_speakers = (
                SpeakerProfile.objects.filter(
                    Q(user__name__icontains=query)
                    | Q(user__email__iexact=query)
                    | Q(user__code__istartswith=query),
                    event__in=full_events,
                )
                .annotate(
                    # We need this subquery to filter out profiles without submissions.
                    has_submission=Exists(
                        Submission.objects.filter(
                            event=OuterRef("event"), speakers__in=OuterRef("user")
                        )
                    )
                )
                .filter(
                    has_submission=True,
                )
                .order_by()
            )

    qs_users = User.objects.none()
    if query and request.user.is_administrator:
        qs_users = (
            User.objects.filter(
                Q(name__icontains=query)
                | Q(email__icontains=query)
                | Q(code__istartswith=query)
            ).order_by("email")
            if query
            else User.objects.none()
        )

    pagesize = 20
    offset = (page - 1) * pagesize
    results = (
        ([serialize_user(request.user)] if show_user else [])
        + [
            serialize_orga(e)
            for e in qs_orga[offset : offset + (pagesize if query else 5)]
        ]
        + [
            serialize_event(e)
            for e in qs_events.select_related("organiser")[
                offset : offset + (pagesize if query else 5)
            ]
        ]
        + [
            serialize_submission(e)
            for e in qs_submissions[offset : offset + (pagesize if query else 5)]
        ]
        + [
            serialize_admin_user(e)
            for e in qs_users[offset : offset + (pagesize if query else 5)]
        ]
        + [
            serialize_speaker(e)
            for e in qs_speakers[offset : offset + (pagesize if query else 5)]
        ]
    )

    if show_user and organiser:
        current_organiser = serialize_orga(organiser)
        if current_organiser in results:
            results.remove(current_organiser)
        results.insert(1, current_organiser)

    total = (
        qs_orga.count()
        + qs_events.count()
        + qs_submissions.count()
        + qs_users.count()
        + qs_speakers.count()
    )
    doc = {"results": results, "pagination": {"more": total >= (offset + pagesize)}}
    return JsonResponse(doc)
