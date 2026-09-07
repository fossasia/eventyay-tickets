"""Keep Video user traits aligned with Organizer → Teams permissions."""

from __future__ import annotations

import logging
from typing import Iterable

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.functions import Upper
from django_scopes import scopes_disabled

from eventyay.base.models.auth import User
from eventyay.eventyay_common.utils import encode_email
from eventyay.eventyay_common.video.permissions import (
    collect_user_video_traits,
    managed_video_trait_values,
    replace_managed_video_traits,
)
from eventyay.features.live.channels import GROUP_USER

logger = logging.getLogger(__name__)


def is_organizer_token_traits(event_slug: str, traits: Iterable[str] | None) -> bool:
    """Check if traits indicate an organizer session (admin, organizer, or managed video traits)."""
    traits_set = set(traits or [])
    if 'admin' in traits_set or f'eventyay-video-event-{event_slug}-organizer' in traits_set:
        return True
    managed = managed_video_trait_values(event_slug)
    return bool(traits_set.intersection(managed))


def check_has_active_staff_session(user, session_key: str | None = None) -> bool:
    """Check if the platform user has an active StaffSession."""
    if not user or not getattr(user, 'is_authenticated', True):
        return False
    if hasattr(user, 'has_active_staff_session'):
        try:
            if session_key:
                return bool(user.has_active_staff_session(session_key))
            return bool(user.has_active_staff_session())
        except Exception:
            pass
    if getattr(user, 'is_staff', False) and getattr(user, 'pk', None):
        try:
            with scopes_disabled():
                from eventyay.base.models.auth import StaffSession
                qs = StaffSession.objects.filter(
                    user=user,
                    date_end__isnull=True,
                )
                if session_key:
                    qs = qs.filter(session_key=session_key)
                return qs.exists()
        except Exception:
            pass
    return False


def is_platform_event_admin(user, session_key: str | None = None) -> bool:
    """Return True if the user is a superuser or has an active staff session."""
    if not user:
        return False
    return bool(
        getattr(user, 'is_superuser', False)
        or check_has_active_staff_session(user, session_key=session_key)
    )


def apply_live_team_video_traits(
    event: Event,
    token_id: str,
    traits: Iterable[str] | None,
    platform_user=None,
    session_key: str | None = None,
) -> list[str]:
    """
    Refresh video traits from the database for the platform user associated with this token.

    Staff video traits are managed only in the team dashboard. If the token
    was issued for an organizer session and maps to a platform account, recompute
    managed traits from current teams.
    Attendee tokens (e.g. ticket purchase) are not upgraded to organizer sessions.
    """
    traits = list(traits or [])
    if not event or not token_id:
        return traits

    if not is_organizer_token_traits(event.slug, traits):
        return traits

    if not platform_user:
        from eventyay.base.services.user import (
            _ticket_lookup,
            resolve_account_fields_by_token_ids,
        )

        account = _ticket_lookup(
            resolve_account_fields_by_token_ids([token_id]),
            token_id,
        )
        if not account:
            return traits

        email = (account.get('email') or '').strip()
        if not email:
            return traits

        with scopes_disabled():
            platform_user = (
                User.objects.filter(event__isnull=True, email__iexact=email)
                .order_by('id')
                .first()
            )
        if not platform_user:
            return traits

    # Fresh team membership after permission edits (avoid request-scoped cache).
    platform_user._teamcache = {}
    permission_set = platform_user.get_event_permission_set(event.organizer, event)
    is_event_admin = is_platform_event_admin(platform_user, session_key=session_key)

    if not is_event_admin and 'admin' in traits:
        traits = [t for t in traits if t != 'admin']
    elif is_event_admin and 'admin' not in traits:
        traits.append('admin')

    return replace_managed_video_traits(
        event.slug,
        traits,
        collect_user_video_traits(event.slug, permission_set),
    )


def force_reload_video_user(user_id) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        GROUP_USER.format(id=str(user_id)),
        {'type': 'connection.reload'},
    )


def sync_video_traits_for_platform_users(
    organizer,
    platform_users: Iterable[User],
    *,
    force_reload: bool = True,
) -> None:
    """
    Update event-scoped Video users for the given platform accounts.

    Recomputes team-managed traits from current Team membership and optionally
    force-reloads connected clients so revoked access applies immediately.
    """
    from eventyay.base.models.auth import StaffSession
    from eventyay.base.services.user import update_user

    users_by_token: dict[str, User] = {}
    for platform_user in platform_users:
        email = (getattr(platform_user, 'email', None) or '').strip()
        if not email:
            continue
        users_by_token[encode_email(email).upper()] = platform_user
    if not users_by_token:
        return

    filter_kwargs = {
        '_token_id_upper__in': list(users_by_token.keys()),
        'deleted': False,
    }
    if organizer:
        filter_kwargs['event__organizer'] = organizer

    with scopes_disabled():
        # Match token_id case-insensitively: JWT uids are uppercased by
        # encode_email, but older rows may store a different case.
        video_users = list(
            User.objects.annotate(_token_id_upper=Upper('token_id'))
            .filter(**filter_kwargs)
            .select_related('event', 'event__organizer')
        )

    for video_user in video_users:
        platform_user = users_by_token.get((video_user.token_id or '').upper())
        if not platform_user or not video_user.event_id:
            continue

        if not is_organizer_token_traits(video_user.event.slug, video_user.traits):
            continue

        is_event_admin = is_platform_event_admin(platform_user)
        current_traits = list(video_user.traits or [])
        if not is_event_admin and 'admin' in current_traits:
            current_traits = [t for t in current_traits if t != 'admin']
        elif is_event_admin and 'admin' not in current_traits:
            current_traits.append('admin')

        platform_user._teamcache = {}
        permission_set = platform_user.get_event_permission_set(
            video_user.event.organizer, video_user.event
        )
        new_traits = replace_managed_video_traits(
            video_user.event.slug,
            current_traits,
            collect_user_video_traits(video_user.event.slug, permission_set),
        )
        if list(video_user.traits or []) == new_traits:
            continue

        update_user(
            video_user.event_id,
            id=video_user.id,
            traits=new_traits,
            serialize=False,
        )
        if force_reload:
            try:
                force_reload_video_user(video_user.id)
            except (OSError, RuntimeError, ConnectionError):
                logger.exception('Failed to force-reload video user %s', video_user.id)


def sync_video_traits_for_team(team, *, members=None, force_reload: bool = True) -> None:
    """Sync Video traits for one team (all members, or an explicit subset)."""
    if members is None:
        members = list(team.members.all())
    else:
        members = list(members)
    organizer = team.organizer
    member_list = members

    def _run():
        sync_video_traits_for_platform_users(
            organizer,
            member_list,
            force_reload=force_reload,
        )

    transaction.on_commit(_run)
