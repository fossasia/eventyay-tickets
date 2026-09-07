import operator
from collections import namedtuple
from datetime import timedelta
from functools import reduce

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.core.paginator import InvalidPage, Paginator
from django.db.models import CharField, Exists, OuterRef, Q
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Lower
from django.db.transaction import atomic
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.eventyay_common.utils import encode_email
from eventyay.features.live.channels import GROUP_USER
from eventyay.base.models import AuditLog
from eventyay.base.models.auth import User
from eventyay.base.models.room import AnonymousInvite
from eventyay.base.models.event import EventView
from eventyay.base.models.orders import Order, OrderPosition
from eventyay.core.permissions import Permission

_WIKI_PROFILE_FIELD_KEYS = (
    "wikimedia_username",
    "wikimania_username",
    "wiki_username",
)

# Non-empty sentinel: Redis cache may not round-trip empty strings reliably.
_EMAIL_HASH_CACHE_MISS = "-"
_EMAIL_HASH_CACHE_TTL = 1800
# Negative account lookups use a shorter TTL and cache.add so a concurrent
# account create can overwrite (or block) a stale miss.
_ACCOUNT_HASH_MISS_TTL = 60


def display_wikimedia_username_from_profile(profile, stored_username):
    if stored_username:
        return stored_username
    fields = (profile or {}).get("fields") or {}
    for key in _WIKI_PROFILE_FIELD_KEYS:
        val = fields.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _is_email_hash_uid_token(token_id):
    if not token_id or len(token_id) != 7:
        return False
    return all(c in "0123456789ABCDEFabcdef" for c in token_id)


def _ticket_lookup(mapping, token_id):
    """Return a ticket/account row dict keyed by token_id (case-insensitive)."""
    if not token_id or not mapping:
        return {}
    if token_id in mapping:
        return mapping[token_id]
    token_upper = token_id.upper()
    for key, value in mapping.items():
        if key.upper() == token_upper:
            return value
    return {}


def _order_email_hash_keys(email):
    """Return upper-case hash keys for an order email (raw and lowercased)."""
    normalized = (email or "").strip()
    if not normalized:
        return ()
    keys = {encode_email(normalized).upper()}
    lowered = normalized.lower()
    if lowered != normalized:
        keys.add(encode_email(lowered).upper())
    return tuple(keys)


def _make_ticket_row(order_code, ticket_code, contact_email):
    return {
        "order_code": order_code,
        "ticket_code": ticket_code,
        "contact_email": (contact_email or "").strip(),
    }


def _email_hash_cache_key(event_id, token_hash):
    return f'video:email_hash:{event_id}:{token_hash}'


def _account_hash_cache_key(token_hash):
    return f'video:account_hash:{token_hash}'


def _set_hash_cache_values(keys, value, ttl=_EMAIL_HASH_CACHE_TTL):
    for key in keys:
        cache.set(key, value, ttl)


def _add_hash_cache_misses(keys, ttl=_ACCOUNT_HASH_MISS_TTL):
    """Store misses only if the key is empty so a concurrent hit wins."""
    for key in keys:
        cache.add(key, _EMAIL_HASH_CACHE_MISS, ttl)


def _cache_email_hash_hits(event_id, email):
    _set_hash_cache_values(
        (_email_hash_cache_key(event_id, h) for h in _order_email_hash_keys(email)),
        email,
    )


def _cache_account_hash_hits(email, wikimedia_username=''):
    """Cache platform account fields for all email-hash variants of an address."""
    payload = {
        'email': email,
        'wikimedia_username': (wikimedia_username or '').strip(),
    }
    _set_hash_cache_values(
        (_account_hash_cache_key(h) for h in _order_email_hash_keys(email)),
        payload,
    )


def invalidate_account_hash_cache_for_emails(emails):
    """
    Drop account-hash cache entries for the given emails.

    Call when a platform account is created or its email / Wikimedia username
    changes so auth does not keep a stale hit or a cached miss.
    Team permission edits do not need this: traits are recomputed live.
    """
    keys = []
    for email in emails:
        for h in _order_email_hash_keys(email):
            keys.append(_account_hash_cache_key(h))
    if keys:
        cache.delete_many(keys)


def refresh_account_hash_cache(email, wikimedia_username=''):
    """Invalidate then write-through current account fields for an email."""
    normalized = (email or '').strip()
    if not normalized:
        return
    invalidate_account_hash_cache_for_emails([normalized])
    _cache_account_hash_hits(normalized, wikimedia_username)


def _unresolved_hash_tokens(token_ids, ticket_by_token):
    return [
        t
        for t in token_ids
        if t and _is_email_hash_uid_token(t) and not _ticket_lookup(ticket_by_token, t)
    ]


def video_contact_email_from_profile(profile):
    return ((profile or {}).get("contact_email") or "").strip()


def video_display_name_from_profile(profile):
    return ((profile or {}).get("display_name") or "").strip()


def admin_users_list_q():
    """Platform accounts plus ticket-only video personas (no duplicate platform email)."""
    contact_email_ref = KeyTextTransform("contact_email", OuterRef("profile"))
    platform_email_match = (
        User.objects.filter(event__isnull=True)
        .exclude(email="")
        .annotate(lower_email=Lower("email"))
        .filter(lower_email=Lower(contact_email_ref))
    )
    return Q(event__isnull=True) | (
        Q(event__isnull=False)
        & ~Q(profile__contact_email="")
        & ~Exists(platform_email_match)
    )


def resolve_video_display_names_by_contact_emails(emails):
    """Map platform contact email to the latest video display name from event personas."""
    uniq = list(dict.fromkeys((e or "").strip().lower() for e in emails if e))
    if not uniq:
        return {}
    email_conditions = reduce(
        operator.or_, (Q(profile__contact_email__iexact=e) for e in uniq), Q()
    )
    result = {}
    with scopes_disabled():
        for row in (
            User.objects.filter(event__isnull=False)
            .filter(email_conditions)
            .order_by("-last_login", "-id")
            .values("profile")
        ):
            profile = row.get("profile") or {}
            email = video_contact_email_from_profile(profile).lower()
            if not email or email in result:
                continue
            display_name = video_display_name_from_profile(profile)
            if display_name:
                result[email] = display_name
    return result


def platform_user_video_display_name(platform_user, video_names_by_email):
    """Display name for admin user list: video persona, then Wikimedia, then nick."""
    email = (platform_user.email or "").strip().lower()
    if email:
        video_name = (video_names_by_email.get(email) or "").strip()
        if video_name:
            return video_name
    wikimedia = (platform_user.wikimedia_username or "").strip()
    if wikimedia:
        return wikimedia
    return (platform_user.nick or "").strip()


def admin_public_fields_from_user_row(user_row, ticket_by_token, account_by_token=None):
    """Admin-only list fields derived from a User values() row and ticket lookup."""
    tid = user_row["token_id"]
    ticket = _ticket_lookup(ticket_by_token, tid)
    account = _ticket_lookup(account_by_token, tid)
    profile = user_row.get("profile") or {}
    return {
        "moderation_state": user_row["moderation_state"],
        "token_id": tid,
        "email": video_contact_email_from_profile(profile)
        or (user_row.get("email") or "").strip()
        or ticket.get("contact_email", "")
        or account.get("email", ""),
        "wikimedia_username": display_wikimedia_username_from_profile(
            profile,
            user_row.get("wikimedia_username") or account.get("wikimedia_username"),
        ),
        "order_code": ticket.get("order_code"),
        "ticket_code": ticket.get("ticket_code"),
    }


def resolve_wikimedia_usernames_by_email(emails):
    """Return a lowercase email -> Wikimedia username map from account users."""
    uniq = list(dict.fromkeys((e or "").strip().lower() for e in emails if e))
    if not uniq:
        return {}
    email_conditions = reduce(
        operator.or_, (Q(email__iexact=e) for e in uniq), Q()
    )
    with scopes_disabled():
        rows = list(
            User.objects.filter(event__isnull=True)
            .filter(email_conditions)
            .exclude(wikimedia_username__isnull=True)
            .exclude(wikimedia_username__exact="")
            .values("email", "wikimedia_username")
        )
    result = {}
    for row in rows:
        email = (row.get("email") or "").strip().lower()
        if email and email not in result:
            result[email] = (row.get("wikimedia_username") or "").strip()
    return result


def resolve_account_fields_by_token_ids(token_ids):
    """Map video JWT uid (email hash) to account email and Wikimedia username.

    Uses a short-TTL cache keyed by email hash so hot paths (Video auth /
    websocket connect) avoid a full platform-user table scan on every call.
    Entries are invalidated when a platform account email/username changes.
    """
    hash_tokens = [t for t in token_ids if t and _is_email_hash_uid_token(t)]
    if not hash_tokens:
        return {}
    wanted = {t.upper() for t in hash_tokens}
    result = {}
    uncached = set()
    for h in wanted:
        val = cache.get(_account_hash_cache_key(h))
        if val is None:
            uncached.add(h)
        elif val and val != _EMAIL_HASH_CACHE_MISS:
            result[h] = val

    if uncached:
        with scopes_disabled():
            for row in (
                User.objects.filter(event__isnull=True)
                .exclude(email__isnull=True)
                .exclude(email__exact="")
                .values("email", "wikimedia_username")
                .iterator(chunk_size=2000)
            ):
                email = (row.get("email") or "").strip()
                if not email:
                    continue
                email_hashes = _order_email_hash_keys(email)
                matched_hashes = [
                    h for h in email_hashes if h in uncached and h not in result
                ]
                if not matched_hashes:
                    continue
                payload = {
                    "email": email,
                    "wikimedia_username": (
                        row.get("wikimedia_username") or ""
                    ).strip(),
                }
                for h in matched_hashes:
                    result[h] = payload
                _cache_account_hash_hits(email, payload["wikimedia_username"])
                uncached.difference_update(email_hashes)
                if not uncached:
                    break
        # Use add() so a concurrent account create/write-through wins over this miss.
        _add_hash_cache_misses(
            _account_hash_cache_key(h) for h in uncached
        )

    return {
        token: result[token.upper()]
        for token in hash_tokens
        if token.upper() in result
    }


def resolve_video_jwt_contact_email(event_id, token_id):
    """
    Resolve the contact email for an event-scoped user created from a video JWT uid.

    Order ticket links use ``encode_email(order.email)`` or a position pseudonym;
    logged-in organisers and talk users use ``encode_email(platform_user.email)``.
    """
    normalized_token = (token_id or "").strip()
    if not normalized_token:
        return None

    ticket_rows = build_admin_ticket_rows_by_token(event_id, [normalized_token])
    ticket = _ticket_lookup(ticket_rows, normalized_token)
    email = (ticket.get("contact_email") or "").strip()
    if email:
        return email.lower()

    if _is_email_hash_uid_token(normalized_token):
        accounts = resolve_account_fields_by_token_ids([normalized_token])
        for key, account in accounts.items():
            if key.upper() == normalized_token.upper():
                email = (account.get("email") or "").strip()
                if email:
                    return email.lower()
    return None


def apply_video_jwt_contact_to_profile(user, event_id, token_id):
    """Store resolved contact email on an event-scoped user's profile (not User.email)."""
    contact_email = resolve_video_jwt_contact_email(event_id, token_id)
    if not contact_email:
        return
    profile = dict(user.profile or {})
    if profile.get("contact_email") == contact_email:
        return
    profile["contact_email"] = contact_email
    user.profile = profile
    user.save(update_fields=["profile"])


def _latest_paid_ticket_row_for_email(event_id, email):
    """Return the latest paid ticket row for an order email on this event."""
    normalized = (email or "").strip()
    if not normalized:
        return None
    with scopes_disabled():
        pos = (
            OrderPosition.objects.filter(
                order__event_id=event_id,
                order__email__iexact=normalized,
                order__status=Order.STATUS_PAID,
                addon_to__isnull=True,
                canceled=False,
            )
            .select_related("order")
            .order_by("-order__datetime", "positionid")
            .first()
        )
    if not pos:
        return None
    return _make_ticket_row(pos.order.code, pos.secret, pos.order.email)


def build_admin_ticket_rows_by_token(event_id, token_ids):
    """
    Map a video user's JWT ``uid`` (stored as ``User.token_id``) to Pretix order data.

    Tokens are either ``OrderPosition.pseudonymization_id`` or ``encode_email(order.email)``
    (seven hex characters) as used by presale video join links.
    """
    uniq = list(dict.fromkeys(t for t in token_ids if t))
    if not uniq:
        return {}
    result = {}
    pseudonym_q = reduce(
        operator.or_, (Q(pseudonymization_id__iexact=t) for t in uniq), Q()
    )
    with scopes_disabled():
        for row in OrderPosition.objects.filter(
            pseudonym_q,
            order__event_id=event_id,
            addon_to__isnull=True,
            canceled=False,
            order__status=Order.STATUS_PAID,
        ).values(
            "pseudonymization_id",
            "secret",
            "order__code",
            "order__email",
        ):
            pid = row["pseudonymization_id"]
            for t in uniq:
                if pid and t and pid.upper() == t.upper() and not _ticket_lookup(result, t):
                    result[t] = _make_ticket_row(
                        row["order__code"], row["secret"], row["order__email"]
                    )
                    break
    need_hash = [
        t
        for t in uniq
        if not _ticket_lookup(result, t) and _is_email_hash_uid_token(t)
    ]
    if need_hash:
        need_hash_upper = {t.upper() for t in need_hash}
        hash_to_email = {}

        # Satisfy as many tokens as possible from the per-token cache.
        # Each entry is small (one email string) and stable — a token_id derived
        # from encode_email(email) never changes for a given address.
        uncached = set()
        for h in need_hash_upper:
            val = cache.get(_email_hash_cache_key(event_id, h))
            if val is not None:
                if val and val != _EMAIL_HASH_CACHE_MISS:
                    hash_to_email[h] = val
                # Sentinel marks a cached negative lookup (no matching email).
            else:
                uncached.add(h)

        # Stream DB only for tokens that were not in cache.
        if uncached:
            with scopes_disabled():
                for email in (
                    Order.objects.filter(event_id=event_id)
                    .filter(status=Order.STATUS_PAID)
                    .exclude(email__isnull=True)
                    .exclude(email__exact="")
                    .values_list('email', flat=True)
                    .iterator(chunk_size=2000)
                ):
                    matched_hash = None
                    for h in _order_email_hash_keys(email):
                        if h in uncached and h not in hash_to_email:
                            matched_hash = h
                            break
                    if matched_hash:
                        hash_to_email[matched_hash] = email
                        _cache_email_hash_hits(event_id, email)
                        uncached.discard(matched_hash)
                        if not uncached:
                            break
        _set_hash_cache_values(
            (
                _email_hash_cache_key(event_id, h)
                for h in need_hash_upper
                if h not in hash_to_email
            ),
            _EMAIL_HASH_CACHE_MISS,
        )

        resolved = [
            hash_to_email[t.upper()]
            for t in need_hash
            if t.upper() in hash_to_email
        ]
        emails = list(dict.fromkeys(resolved))
        positions_by_email = {}
        if emails:
            email_conditions = reduce(
                operator.or_, (Q(order__email__iexact=e) for e in emails), Q()
            )
            with scopes_disabled():
                rows = (
                    OrderPosition.objects.filter(
                        email_conditions,
                        order__event_id=event_id,
                        order__status=Order.STATUS_PAID,
                        addon_to__isnull=True,
                        canceled=False,
                    )
                    .select_related("order")
                    .order_by("order__email", "-order__datetime", "positionid")
                )
                for pos in rows:
                    key = (pos.order.email or "").strip().lower()
                    if key and key not in positions_by_email:
                        positions_by_email[key] = _make_ticket_row(
                            pos.order.code, pos.secret, pos.order.email
                        )
        for t in need_hash:
            email = hash_to_email.get(t.upper())
            if not email:
                continue
            row = positions_by_email.get(email.strip().lower())
            if row:
                result[t] = dict(row)
    return result


def build_admin_ticket_lookups(event_id, token_ids):
    """Return ticket and account lookup maps for admin user list fields."""
    uniq = list(dict.fromkeys(t for t in token_ids if t))
    ticket_by_token = build_admin_ticket_rows_by_token(event_id, uniq)
    unresolved = _unresolved_hash_tokens(uniq, ticket_by_token)
    account_by_token = (
        resolve_account_fields_by_token_ids(unresolved) if unresolved else {}
    )
    for token in unresolved:
        email = (_ticket_lookup(account_by_token, token).get("email") or "").strip()
        if not email:
            continue
        row = _latest_paid_ticket_row_for_email(event_id, email)
        if row:
            ticket_by_token[token] = row
            _cache_email_hash_hits(event_id, email)
    return ticket_by_token, account_by_token


def _resolve_admin_fields_for_users(event_id, users_data):
    """Build admin-only list fields for event-scoped user rows."""
    if not users_data:
        return {}
    token_ids = [u["token_id"] for u in users_data if u.get("token_id")]
    ticket_by_token, account_by_token = build_admin_ticket_lookups(event_id, token_ids)
    admin_fields_by_id = {}
    emails_to_resolve = []
    for u in users_data:
        fields = admin_public_fields_from_user_row(
            u, ticket_by_token, account_by_token
        )
        admin_fields_by_id[u["id"]] = fields
        if fields.get("email") and not fields.get("wikimedia_username"):
            emails_to_resolve.append(fields["email"])
    if emails_to_resolve:
        email_to_wikimedia = resolve_wikimedia_usernames_by_email(emails_to_resolve)
        for fields in admin_fields_by_id.values():
            if not fields.get("wikimedia_username"):
                email = (fields.get("email") or "").strip().lower()
                if email and email in email_to_wikimedia:
                    fields["wikimedia_username"] = email_to_wikimedia[email]
    return admin_fields_by_id


def get_user_by_id(event_id, user_id):
    try:
        return User.objects.get(id=user_id, event_id=event_id)
    except User.DoesNotExist:
        return


def get_user_by_token_id(event_id, token_id):
    try:
        return User.objects.get(token_id=token_id, event_id=event_id)
    except User.DoesNotExist:
        return


def get_user_by_client_id(event_id, client_id):
    try:
        return User.objects.get(client_id=client_id, event_id=event_id)
    except User.DoesNotExist:
        return


@database_sync_to_async
def get_public_user(event_id, id, include_admin_info=False, trait_badges_map=None):
    user = get_user_by_id(event_id, id)
    if not user:
        return None
    data = user.serialize_public(
        include_admin_info=include_admin_info,
        trait_badges_map=trait_badges_map,
        include_client_state=include_admin_info and user.type == User.UserType.KIOSK,
    )
    if include_admin_info:
        admin_fields = _resolve_admin_fields_for_users(
            event_id,
            [
                {
                    "id": user.id,
                    "token_id": user.token_id,
                    "moderation_state": user.moderation_state,
                    "email": user.email or "",
                    "wikimedia_username": user.wikimedia_username or "",
                    "profile": user.profile,
                }
            ],
        ).get(user.id, {})
        data.update(admin_fields)
    return data


@database_sync_to_async
def get_public_users(
    event_id,
    *,
    ids=None,
    pretalx_ids=None,
    include_admin_info=False,
    trait_badges_map=None,
    include_banned=True,
    require_show_publicly=False,
    type=User.UserType.PERSON,
):
    # This method is called a lot, especially when lots of people join at once (event start, server reboot, …)
    # For performance reasons, we therefore do not initialize model instances and use serialize_public()
    if ids is not None:
        qs = User.objects.filter(id__in=ids, event_id=event_id)
    else:
        qs = User.objects.filter(event_id=event_id, deleted=False).order_by(
            "profile__display_name", "id"
        )
    if require_show_publicly:
        qs = qs.filter(show_publicly=True)
    if pretalx_ids is not None:
        qs = qs.filter(pretalx_id__in=pretalx_ids)
    if type is not None:
        qs = qs.filter(type=type)
    if not include_banned:
        qs = qs.exclude(moderation_state=User.ModerationState.BANNED)

    value_fields = (
        "id",
        "type",
        "profile",
        "deleted",
        "moderation_state",
        "token_id",
        "traits",
        "last_login",
        "pretalx_id",
        "client_state",
    )

    if include_admin_info:
        users_data = list(qs.values(*value_fields, "email", "wikimedia_username"))
    else:
        users_data = qs.values(*value_fields).iterator()

    admin_fields_by_id = (
        _resolve_admin_fields_for_users(event_id, users_data)
        if include_admin_info and users_data
        else {}
    )

    return [
        dict(
            id=str(u["id"]),
            profile=u["profile"],
            pretalx_id=u["pretalx_id"],
            deleted=u["deleted"],
            inactive=(
                u["last_login"] is None or u["last_login"] < now() - timedelta(hours=36)
            ),
            badges=(
                sorted(
                    list(
                        {
                            badge
                            for trait, badge in trait_badges_map.items()
                            if trait in u["traits"]
                        }
                    )
                )
                if trait_badges_map
                else []
            ),
            **(
                {"client_state": u["client_state"]}
                if include_admin_info and u["type"] == User.UserType.KIOSK
                else {}
            ),
            **(
                admin_fields_by_id.get(u["id"], {})
                if include_admin_info
                else {}
            ),
        )
        for u in users_data
    ]


def get_user(
    event=None,
    *,
    with_id=None,
    with_token=None,
    with_client_id=None,
    with_invite_token=None,
    with_platform_user=None,
    with_session_key=None,
):
    if with_id:
        user = get_user_by_id(event.id, with_id)
        return user

    token_id = None
    anonymous_invite = None
    token_traits = None
    if with_platform_user:
        from eventyay.eventyay_common.video.traits_sync import (
            apply_live_team_video_traits,
            is_platform_event_admin,
        )
        from eventyay.eventyay_common.video.permissions import video_attendee_trait
        from eventyay.eventyay_common.utils import encode_email

        token_id = encode_email(with_platform_user.email)
        permission_set = with_platform_user.get_event_permission_set(event.organizer, event)
        is_event_admin = is_platform_event_admin(with_platform_user, session_key=with_session_key)
        base_traits = ['attendee', video_attendee_trait(event.slug)]
        if is_event_admin:
            base_traits.extend(['admin', f'eventyay-video-event-{event.slug}-organizer'])
        elif permission_set:
            base_traits.append(f'eventyay-video-event-{event.slug}-organizer')

        token_traits = apply_live_team_video_traits(
            event, token_id, base_traits, platform_user=with_platform_user, session_key=with_session_key
        )
        user = get_user_by_token_id(event.id, token_id)
        if not user:
            user = create_user(
                event_id=event.id,
                token_id=token_id,
                traits=token_traits,
                profile={
                    'display_name': with_platform_user.fullname or with_platform_user.email.split('@')[0],
                    'contact_email': with_platform_user.email,
                },
            )
            return user
    elif with_token:
        from eventyay.eventyay_common.video.traits_sync import apply_live_team_video_traits

        token_id = with_token["uid"]
        # Team Video traits must follow live Organizer → Teams grants, not a cached JWT.
        token_traits = apply_live_team_video_traits(
            event, token_id, with_token.get("traits")
        )
        user = get_user_by_token_id(event.id, token_id)
    elif with_client_id:
        user = get_user_by_client_id(event.id, with_client_id)
        if not user and with_invite_token:
            try:
                anonymous_invite = AnonymousInvite.objects.get(
                    short_token=with_invite_token,
                    event=event,
                    expires__gte=now(),
                )
            except AnonymousInvite.DoesNotExist:
                return None
    else:
        raise Exception(
            "get_user was called without valid with_token, with_id, with_platform_user or with_client_id"
        )

    if user:
        if with_token or with_platform_user:
            if set(user.traits or []) != set(token_traits or []):
                update_user(event.id, id=user.id, traits=token_traits, serialize=False)
                user = get_user_by_id(event.id, user.id)
            if token_id:
                apply_video_jwt_contact_to_profile(user, event.id, token_id)
        return user

    traits = token_traits if with_token else None
    if not anonymous_invite and not event.has_permission_implicit(
        traits=traits or [],
        permissions=[Permission.EVENT_VIEW],
    ):
        # There is no chance this user gets in, we want to do an early out to prevent empty
        # user profiles from being created
        return

    if token_id:
        contact_email = resolve_video_jwt_contact_email(event.id, token_id)
        profile = with_token.get("profile") if with_token else None
        if contact_email:
            profile = dict(profile or {})
            profile["contact_email"] = contact_email
        user = create_user(
            event_id=event.id,
            token_id=token_id,
            profile=profile,
            traits=traits,
            pretalx_id=with_token.get("pretalx_id") if with_token else None,
        )
    else:
        user = create_user(
            event_id=event.id,
            client_id=with_client_id,
            anonymous_invite=anonymous_invite,
            traits=traits,
        )
    return user


def create_user(
    event_id,
    *,
    token_id=None,
    client_id=None,
    traits=None,
    profile=None,
    pretalx_id=None,
    anonymous_invite=None,
):
    kwargs = {}
    if anonymous_invite:
        kwargs.update(
            {
                "type": User.UserType.ANONYMOUS,
                "show_publicly": False,
            }
        )
    user = User.objects.create(
        event_id=event_id,
        token_id=token_id,
        client_id=client_id,
        pretalx_id=pretalx_id,
        traits=traits or [],
        profile=profile or {},
        **kwargs,
    )
    if anonymous_invite:
        user.event_grants.create(event_id=event_id, role="__anonymous_event")
        user.room_grants.create(
            event_id=event_id,
            room_id=anonymous_invite.room_id,
            role="__anonymous_room",
        )
    return user


@atomic
def update_user(
    event_id, id, *, traits=None, data=None, is_admin=False, serialize=True
):
    # TODO: Exception handling
    user = (
        User.objects.select_related("event")
        .select_for_update()
        .get(id=id, event_id=event_id)
    )

    if traits is not None:
        if user.traits != traits:
            AuditLog.objects.create(
                event_id=event_id,
                user=user,
                type="auth.user.traits.changed",
                data={
                    "object": str(user.pk),
                    "old": user.traits,
                    "new": traits,
                },
            )
            user.traits = traits
        user.save(update_fields=["traits"])

    if data is not None:
        save_fields = []
        if "profile" in data and data["profile"] != user.profile:
            AuditLog.objects.create(
                event_id=event_id,
                user=user,
                type="auth.user.profile.changed",
                data={
                    "object": str(user.pk),
                    "old": user.profile,
                    "new": data["profile"],
                    "is_admin": is_admin,
                },
            )

            # TODO: Anything we want to validate here?
            user.profile = data.get("profile")
            save_fields.append("profile")

        if is_admin and "pretalx_id" in data and data["pretalx_id"] != user.pretalx_id:
            AuditLog.objects.create(
                event_id=event_id,
                user=user,
                type="auth.user.pretalx_id.changed",
                data={
                    "object": str(user.pk),
                    "old": user.pretalx_id,
                    "new": data["pretalx_id"],
                },
            )
            user.pretalx_id = data.get("pretalx_id")
            save_fields.append("pretalx_id")

        if (
            not is_admin
            and "client_state" in data
            and data["client_state"] != user.client_state
        ) or (
            is_admin
            and user.type == User.UserType.KIOSK
            and "client_state" in data
            and data["client_state"] != user.client_state
        ):
            user.client_state = data.get("client_state")
            save_fields.append("client_state")
            # Legacy eventyay-talk favourite syncing was removed.

        if save_fields:
            user.save(update_fields=save_fields)

    return (
        user.serialize_public(
            trait_badges_map=user.event.config.get("trait_badges_map")
        )
        if serialize
        else user
    )



def start_view(user: User, delete=False):
    # The majority of EventView that go "abandoned" (i.e. ``end`` is never set) are likely caused by server
    # crashes or restarts, in which case ``end`` can't be set. However, after a server crash, the client
    # either reconnects automatically or the user will attempt a reconnect themselves through a page reload,
    # so the most likely end of the previous session is "just before this", and the best assumption is to set
    # the end to "now".
    #
    # Obviously, this is wrong whenever a user has multiple sessions open, e.g. if the same user has the room
    # open in browser A and then opens the same room in browser B, this will set the ``end`` for the session
    # in browser A, even though it's already running. It doesn't matter, though! First, for all our statistics
    # we only count unique users and the result "this user was present at the time" is still correct. Second,
    # the way ``end_view`` is implemented, the session from browser A will still be corrected with the accurate
    # time as soon as browser A leaves.
    previous = EventView.objects.filter(
        user=user, event_id=user.event_id, end__isnull=True
    )
    if delete:
        previous.delete()
    else:
        previous.update(end=now())
    r = EventView.objects.create(event_id=user.event_id, user=user)
    return r


def end_view(view: EventView, delete=False):
    if delete:
        if view.pk:
            view.delete()
    else:
        view.end = now()
        view.save()


LoginResult = namedtuple(
    "LoginResult",
    "user event_config chat_channels chat_notification_counts view",
)


class AuthError(Exception):
    def __init__(self, code):
        self.code = code


def login(
    *,
    event=None,
    token=None,
    client_id=None,
    invite_token=None,
    platform_user=None,
    session_key=None,
) -> LoginResult:
    from .chat import ChatService
    from .event import get_event_config_for_user

    user = get_user(
        event=event,
        with_client_id=client_id,
        with_token=token,
        with_invite_token=invite_token,
        with_platform_user=platform_user,
        with_session_key=session_key,
    )

    if user and user.is_banned:
        raise AuthError("auth.denied")

    if not user or not event.has_permission(
        user=user, permission=Permission.EVENT_VIEW
    ):
        if token:
            raise AuthError("auth.denied")
        else:
            raise AuthError("auth.missing_token")

    event_config_obj = getattr(event, "config", None) or {}
    track_event_views = bool(event_config_obj.get("track_event_views", True))

    user.last_login = now()
    user.save(update_fields=["last_login"])

    if track_event_views:
        view = start_view(user)
    else:
        view = None

    return LoginResult(
        user=user,
        event_config=get_event_config_for_user(event, user),
        chat_channels=ChatService(event).get_channels_for_user(
            user.pk, is_volatile=False
        ),
        chat_notification_counts=ChatService(event).get_notification_counts(user.pk),
        view=view,
    )


@database_sync_to_async
@atomic
def get_blocked_users(user, event) -> bool:
    return [
        u.serialize_public(trait_badges_map=event.config.get("trait_badges_map"))
        for u in user.blocked_users.all()
    ]


@database_sync_to_async
@atomic
def set_user_banned(event, user_id, by_user) -> bool:
    user = get_user_by_id(event_id=event.pk, user_id=user_id)
    if not user:
        return False
    user.moderation_state = User.ModerationState.BANNED
    user.save(update_fields=["moderation_state"])

    AuditLog.objects.create(
        event=event,
        user=by_user,
        type="auth.user.banned",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def delete_user(event, user_id, by_user) -> bool:
    user = get_user_by_id(event_id=event.pk, user_id=user_id)
    if not user:
        return False
    user.soft_delete()

    AuditLog.objects.create(
        event=event,
        user=by_user,
        type="auth.user.deleted",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def set_user_silenced(event, user_id, by_user) -> bool:
    user = get_user_by_id(event_id=event.pk, user_id=user_id)
    if not user:
        return False
    if user.moderation_state == User.ModerationState.BANNED:
        return True
    user.moderation_state = User.ModerationState.SILENCED
    user.save(update_fields=["moderation_state"])
    AuditLog.objects.create(
        event=event,
        user=by_user,
        type="auth.user.silenced",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def set_user_free(event, user_id, by_user) -> bool:
    user = get_user_by_id(event_id=event.pk, user_id=user_id)
    if not user:
        return False
    user.moderation_state = User.ModerationState.NONE
    user.save(update_fields=["moderation_state"])
    AuditLog.objects.create(
        event=event,
        user=by_user,
        type="auth.user.reactivated",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def block_user(event, blocking_user: User, blocked_user_id) -> bool:
    blocked_user = get_user_by_id(event_id=event.pk, user_id=blocked_user_id)
    if not blocked_user:
        return False

    blocking_user.blocked_users.add(blocked_user)
    blocked_user.touch()
    AuditLog.objects.create(
        event=event,
        user=blocking_user,
        type="auth.user.blocked",
        data={
            "object": blocked_user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def unblock_user(event, blocking_user: User, blocked_user_id) -> bool:
    blocked_user = get_user_by_id(event_id=event.pk, user_id=blocked_user_id)
    if not blocked_user:
        return False

    blocking_user.blocked_users.remove(blocked_user)
    blocked_user.touch()
    AuditLog.objects.create(
        event=event,
        user=blocking_user,
        type="auth.user.unblocked",
        data={
            "object": blocked_user_id,
        },
    )
    return True


@database_sync_to_async
def list_users(
    event_id,
    page,
    page_size,
    search_term,
    search_fields=None,
    badge=None,
    trait_badges_map=None,
    include_banned=True,
    include_admin_info=False,
    include_private=False,
) -> object:
    qs = (
        User.objects.filter(
            event_id=event_id,
            deleted=False,
            type=User.UserType.PERSON,
        )
        .exclude(profile__display_name__isnull=True)
        .exclude(profile__display_name__exact="")
    )
    if not include_private:
        qs = qs.filter(show_publicly=True)
    if not include_banned:
        qs = qs.exclude(moderation_state=User.ModerationState.BANNED)
    if badge:
        conditions = []
        if trait_badges_map:
            for t_trait, t_badge in trait_badges_map.items():
                if t_badge == badge:
                    conditions.append(Q(traits__contains=[t_trait]))
        if conditions:
            qs = qs.filter(reduce(operator.or_, conditions))
        else:
            qs = qs.none()

    if search_term:
        conditions = [(Q(profile__display_name__icontains=search_term))]
        search_fields = search_fields or []
        for field in search_fields:
            conditions.append(
                Q(**{"profile__fields__" + field + "__icontains": search_term})
            )

        if include_admin_info:
            conditions.append(Q(token_id__icontains=search_term))
            conditions.append(
                Q(email__icontains=search_term) | Q(profile__contact_email__icontains=search_term)
            )
            conditions.append(Q(wikimedia_username__icontains=search_term))

            qs = qs.annotate(id_text=Cast('id', output_field=CharField()))
            conditions.append(Q(id_text__istartswith=search_term))

            with scopes_disabled():
                matching_tokens = set(
                    OrderPosition.objects.filter(
                        Q(secret__icontains=search_term) | Q(order__code__icontains=search_term),
                        order__event_id=event_id,
                    ).values_list("pseudonymization_id", flat=True)
                )
            if matching_tokens:
                conditions.append(Q(token_id__in=[t for t in matching_tokens if t]))

        qs = qs.filter(reduce(operator.or_, conditions))

    try:
        value_fields = (
            "id",
            "profile",
            "traits",
            "last_login",
            "moderation_state",
            "token_id",
            "pretalx_id",
        )
        if include_admin_info:
            qs_values = qs.order_by("profile__display_name").values(
                *value_fields,
                "email",
                "wikimedia_username",
            )
        else:
            qs_values = qs.order_by("profile__display_name").values(*value_fields)
        p = Paginator(
            qs_values,
            page_size,
        ).page(page)
        admin_fields_by_id = (
            _resolve_admin_fields_for_users(event_id, p.object_list)
            if include_admin_info and p.object_list
            else {}
        )
        return {
            "results": sorted(
                (
                    dict(
                        id=str(u["id"]),
                        profile=u["profile"],
                        pretalx_id=u["pretalx_id"],
                        inactive=u["last_login"] is None
                        or u["last_login"] < now() - timedelta(hours=36),
                        badges=(
                            sorted(
                                list(
                                    {
                                        badge
                                        for trait, badge in trait_badges_map.items()
                                        if trait in u["traits"]
                                    }
                                )
                            )
                            if trait_badges_map
                            else []
                        ),
                        **(
                            admin_fields_by_id.get(u["id"], {})
                            if include_admin_info
                            else {}
                        ),
                    )
                    for u in p.object_list
                ),
                key=lambda u: (
                    u["profile"]["display_name"].lower(),
                    int(u["inactive"] or 0),
                ),
            ),
            "isLastPage": not p.has_next(),
        }
    except InvalidPage:
        return {
            "results": [],
            "isLastPage": True,
        }


async def user_broadcast(event_type, data, user_id, socket_id):
    await get_channel_layer().group_send(
        GROUP_USER.format(id=user_id),
        {
            "type": "user.broadcast",
            "event_type": event_type,
            "data": data,
            "socket": socket_id,
        },
    )
