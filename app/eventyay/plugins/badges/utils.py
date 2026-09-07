import json
import logging

from django.core.cache import cache as default_cache
from django.db.models import Exists, OuterRef
from django.utils.translation import gettext_lazy as _

from eventyay.base.pdf import get_variables

from .models import BadgeLayout, BadgeProduct, BadgeVoucher


logger = logging.getLogger(__name__)


BADGE_HIDDEN_FIELDS_KEY = 'badge_hidden_fields'
BADGE_FIELD_OVERRIDES_KEY = 'badge_field_overrides'
BADGE_FIELD_OVERRIDE_MAX_LENGTH = 190
BADGE_TICKET_PROVIDER = 'badge'
BADGE_LAYOUT_PERSISTED_FIELDS = (
    'layout',
    'ask_user_fields',
    'required_badge_fields',
    'allow_customization',
    'allow_badge_editing',
    'background',
    'default',
)

DEFAULT_BADGE_ENABLED_PLACEHOLDERS = (
    'attendee_name',
    'attendee_company',
    'attendee_job_title',
    'product',
    'event_name',
    'event_date',
    'secret',
)

DEFAULT_BADGE_ENABLED_PLACEHOLDERS_SET = frozenset(DEFAULT_BADGE_ENABLED_PLACEHOLDERS)

BADGE_PLACEHOLDER_CATEGORIES = (
    ('attendee', _('Attendee Information')),
    ('event', _('Event Details')),
    ('product_order', _('Product & Order')),
    ('questions', _('Custom Questions')),
    ('invoice', _('Invoice & Billing')),
    ('misc', _('Seating & Miscellaneous')),
)

_PRODUCT_ORDER_PLACEHOLDERS = frozenset({
    'product',
    'variation',
    'productvar',
    'product_description',
    'productvar_description',
    'product_category',
    'price',
    'price_with_addons',
    'ticket_validity',
    'order',
    'positionid',
    'secret',
    'addons',
    'telephone',
    'email',
})

_renderer_cache = {}
_ASSIGNMENT_CACHE_ATTR = '_badge_layout_assignment_cache'


def get_placeholder_category(key: str) -> str:
    if key.startswith('question_'):
        return 'questions'
    if key.startswith('attendee_'):
        return 'attendee'
    if key.startswith('event_'):
        return 'event'
    if key.startswith('invoice_'):
        return 'invoice'
    if key in _PRODUCT_ORDER_PLACEHOLDERS:
        return 'product_order'
    return 'misc'


def get_event_allowed_badge_placeholders(event) -> list[str]:
    if not event:
        return list(DEFAULT_BADGE_ENABLED_PLACEHOLDERS)

    raw = event.settings.get('badge_allowed_placeholders')
    if raw is None or raw == '':
        return list(DEFAULT_BADGE_ENABLED_PLACEHOLDERS)
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
            if isinstance(val, list):
                return [str(item) for item in val]
        except (ValueError, TypeError):
            return list(DEFAULT_BADGE_ENABLED_PLACEHOLDERS)
    elif isinstance(raw, (list, tuple)):
        return [str(item) for item in raw]
    return list(DEFAULT_BADGE_ENABLED_PLACEHOLDERS)


def get_categorized_badge_placeholders(event) -> list[dict]:
    variables = _get_cached_badge_variables(event)
    category_map = {
        cat_id: {'id': cat_id, 'label': str(cat_label), 'items': []}
        for cat_id, cat_label in BADGE_PLACEHOLDER_CATEGORIES
    }

    for varname, var in variables.items():
        if var.get('canonical_key', varname) != varname:
            continue
        cat_id = get_placeholder_category(varname)
        category_map[cat_id]['items'].append(
            {
                'key': varname,
                'label': str(var.get('label', varname)),
                'sample': str(var.get('editor_sample', '')),
            }
        )

    return [cat for cat in category_map.values() if cat['items']]


def _badge_version_key(event):
    """Return a cache key outside the NamespacedCache namespace.

    ``event.cache`` is a ``NamespacedCache`` whose ``clear()`` rotates a
    namespace prefix — making every previously stored key unreachable.
    Because dozens of unrelated model saves (products, settings, …) call
    ``event.cache.clear()``, storing the badge layout version *inside*
    that namespace caused it to silently reset to 0.

    By using Django's default cache directly with a simple key, we avoid
    the namespace entirely while still sharing state across all processes
    via the same Redis backend.
    """
    return f'badge_layout_version:{event.pk}'


def get_badge_layout_version(event):
    """
    Return the current badge layout/rendering cache version for this event.

    This is stored in the shared (cross-process/cross-worker) cache backend, so every
    Celery worker and web worker will observe a version bump immediately on their next
    lookup, no matter which process actually saved the layout change.
    """
    return default_cache.get(_badge_version_key(event)) or 0


def get_badge_layout_renderer_token(layout):
    """Return a content token used as part of the in-process renderer cache key."""
    if layout is None:
        return None
    background = layout.background.name if layout.background else ''
    return (
        layout.layout or '',
        layout.ask_user_fields or '',
        layout.required_badge_fields or '',
        bool(layout.allow_customization),
        bool(getattr(layout, 'allow_badge_editing', False)),
        background,
    )


def reset_badge_layout_assignment_cache(event):
    """Drop the per-Event assignment snapshot used within a process."""
    if hasattr(event, _ASSIGNMENT_CACHE_ATTR):
        delattr(event, _ASSIGNMENT_CACHE_ATTR)


def delete_badge_cached_pdfs(event):
    """Delete persisted badge PDF cache rows for one event."""
    from eventyay.base.models import CachedCombinedTicket, CachedTicket

    CachedTicket.objects.filter(
        order_position__order__event=event,
        provider=BADGE_TICKET_PROVIDER,
    ).delete()
    CachedCombinedTicket.objects.filter(
        order__event=event,
        provider=BADGE_TICKET_PROVIDER,
    ).delete()


def clear_badge_layout_cache(event):
    reset_badge_layout_assignment_cache(event)
    for attr in ('_badge_layouts_exist', '_badge_pdf_variables'):
        if hasattr(event, attr):
            delattr(event, attr)

    # Bump the layout version in the cross-process cache so every worker's in-memory
    # renderer cache is invalidated on its very next use, without needing to reach into
    # other processes' memory.
    #
    # We use Django's default cache directly (not event.cache) so the version survives
    # event.cache.clear() calls triggered by unrelated model saves.
    key = _badge_version_key(event)
    version = default_cache.get(key) or 0
    default_cache.set(key, version + 1, 3600 * 24 * 30)

    stale_keys = [cache_key for cache_key in _renderer_cache if cache_key[0] == event.pk]
    for cache_key in stale_keys:
        del _renderer_cache[cache_key]


def normalize_badge_content_key(content):
    return 'event_name' if content == 'item' else content


def get_badge_layout_assignment_maps(event):
    """
    Resolve product/voucher/default layout assignments.

    Cached on the Event instance only for the current layout version, so default
    switches and assignment edits are picked up as soon as the version bumps.
    """
    version = get_badge_layout_version(event)
    cached = getattr(event, _ASSIGNMENT_CACHE_ATTR, None)
    if cached is not None and cached[0] == version:
        return cached[1]

    product_map = {
        assignment.product_id: assignment.layout
        for assignment in BadgeProduct.objects.select_related('layout').filter(product__event=event)
    }
    voucher_map = {
        assignment.voucher_id: assignment.layout
        for assignment in BadgeVoucher.objects.select_related('layout').filter(voucher__event=event)
    }
    try:
        default_layout = event.badge_layouts.get(default=True)
    except BadgeLayout.DoesNotExist:
        default_layout = None

    maps = (product_map, voucher_map, default_layout)
    setattr(event, _ASSIGNMENT_CACHE_ATTR, (version, maps))
    return maps


def get_badge_layout_for_position(event, position):
    product_map, voucher_map, default_layout = get_badge_layout_assignment_maps(event)

    if position.voucher_id and position.voucher_id in voucher_map:
        return voucher_map[position.voucher_id]

    if position.product_id in product_map:
        return product_map[position.product_id]
    return default_layout


def resolve_badge_layout_override(event, layout_id):
    """Return a BadgeLayout for ``layout_id`` belonging to ``event``, or None.

    Raises ``ValidationError`` when ``layout_id`` is provided but invalid.
    """
    from django.core.exceptions import ValidationError as DjangoValidationError

    if layout_id is None or layout_id == '':
        return None
    try:
        pk = int(layout_id)
    except (TypeError, ValueError) as exc:
        raise DjangoValidationError(_('Invalid badge layout id.')) from exc
    try:
        return event.badge_layouts.get(pk=pk)
    except BadgeLayout.DoesNotExist as exc:
        raise DjangoValidationError(_('Unknown badge layout.')) from exc


def position_has_printable_badge(event, position):
    return get_badge_layout_for_position(event, position) is not None


def exclude_explicit_no_badge(qs, assignment_model, fk_lookup):
    return qs.annotate(
        no_badging=Exists(
            assignment_model.objects.filter(**{fk_lookup: OuterRef('pk'), 'layout__isnull': True})
        )
    ).exclude(no_badging=True)


def get_badge_hidden_fields(position):
    config_position = get_badge_config_position(position)
    root_question_form_data = config_position.meta_info_data.get('question_form_data', {})
    if BADGE_HIDDEN_FIELDS_KEY in root_question_form_data:
        hidden_fields = root_question_form_data[BADGE_HIDDEN_FIELDS_KEY]
    else:
        hidden_fields = position.meta_info_data.get('question_form_data', {}).get(BADGE_HIDDEN_FIELDS_KEY, [])
    if isinstance(hidden_fields, str):
        return [hidden_fields]
    return hidden_fields


def invalidate_badge_cache_for_position(position):
    from eventyay.base.models import CachedCombinedTicket, CachedFile, CachedTicket

    position_ids = [bundle_position.pk for bundle_position in get_badge_bundle_positions(position)]
    CachedTicket.objects.filter(
        order_position_id__in=position_ids,
        provider=BADGE_TICKET_PROVIDER,
    ).delete()
    for position_id in position_ids:
        CachedFile.objects.filter(filename__startswith=f'badge_{position_id}_').delete()
    order_id = getattr(position, 'order_id', None)
    if order_id:
        CachedCombinedTicket.objects.filter(order=order_id, provider=BADGE_TICKET_PROVIDER).delete()


def invalidate_badge_cache_for_order(order):
    from eventyay.base.models import CachedCombinedTicket, CachedTicket

    CachedTicket.objects.filter(order_position__order=order, provider=BADGE_TICKET_PROVIDER).delete()
    CachedCombinedTicket.objects.filter(order=order, provider=BADGE_TICKET_PROVIDER).delete()


def get_badge_field_overrides(position):
    config_position = get_badge_config_position(position)
    root_question_form_data = config_position.meta_info_data.get('question_form_data', {})
    raw = root_question_form_data.get(BADGE_FIELD_OVERRIDES_KEY)
    if raw is None:
        raw = position.meta_info_data.get('question_form_data', {}).get(BADGE_FIELD_OVERRIDES_KEY, {})
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def _badge_customization_layout(event, position):
    from django.core.exceptions import ValidationError

    layout = get_badge_layout_for_position(event, position)
    if not layout or not layout.allow_customization:
        raise ValidationError(_('Badge customization is not allowed for this ticket.'))
    return layout


def validate_badge_hidden_fields(event, position, hidden_fields):
    from django.core.exceptions import ValidationError

    if 'eventyay.plugins.badges' not in event.plugins:
        raise ValidationError(_('Badge customization is not enabled for this event.'))

    _badge_customization_layout(event, position)

    allowed_keys = {key for key, _ in get_badge_bundle_option_choices(event, position)}
    if hidden_fields is None:
        normalized = []
    elif isinstance(hidden_fields, str):
        normalized = [hidden_fields]
    elif isinstance(hidden_fields, (list, tuple)):
        normalized = [str(value) for value in hidden_fields]
    else:
        raise ValidationError(_('badge_hidden_fields must be a list of field keys.'))
    invalid_keys = sorted({key for key in normalized if key not in allowed_keys})
    if invalid_keys:
        raise ValidationError(
            _('Invalid badge field keys: {keys}').format(keys=', '.join(invalid_keys))
        )

    layout = _badge_customization_layout(event, position)
    required_keys = set(layout.required_badge_fields_data)
    hidden_required = required_keys & set(normalized)
    if hidden_required:
        raise ValidationError(
            _('Badge field(s) {keys} are required and cannot be hidden.').format(
                keys=', '.join(sorted(hidden_required))
            )
        )

    return normalized


def save_badge_hidden_fields(position, hidden_fields):
    save_badge_customization(position, hidden_fields=hidden_fields)


def validate_badge_field_overrides(event, position, field_overrides):
    from django.core.exceptions import ValidationError

    if 'eventyay.plugins.badges' not in event.plugins:
        raise ValidationError(_('Badge customization is not enabled for this event.'))

    layout = _badge_customization_layout(event, position)
    if not layout.allow_badge_editing:
        raise ValidationError(_('Badge editing is not allowed for this ticket.'))

    allowed_keys = {key for key, _label in get_badge_bundle_option_choices(event, position)}
    if field_overrides is None:
        return {}
    if not isinstance(field_overrides, dict):
        raise ValidationError(_('badge_field_overrides must be an object of field keys to text values.'))

    normalized = {}
    for key, value in field_overrides.items():
        field_key = str(key)
        if field_key not in allowed_keys:
            raise ValidationError(
                _('Invalid badge field keys: {keys}').format(keys=', '.join(sorted({field_key})))
            )
        text = str(value or '').strip()
        if len(text) > BADGE_FIELD_OVERRIDE_MAX_LENGTH:
            raise ValidationError(
                _('Badge field text for {key} is too long.').format(key=field_key)
            )
        if text:
            normalized[field_key] = text
    return normalized


def save_badge_customization(position, *, hidden_fields=None, field_overrides=None):
    config_position = get_badge_config_position(position)
    meta = dict(config_position.meta_info_data or {})
    question_form_data = dict(meta.get('question_form_data', {}))
    changed = False

    if hidden_fields is not None:
        new_hidden = list(hidden_fields)
        current_hidden = get_badge_hidden_fields(position)
        if sorted(new_hidden) != sorted(current_hidden):
            question_form_data[BADGE_HIDDEN_FIELDS_KEY] = new_hidden
            changed = True

    if field_overrides is not None:
        new_overrides = dict(field_overrides)
        if new_overrides != get_badge_field_overrides(position):
            question_form_data[BADGE_FIELD_OVERRIDES_KEY] = new_overrides
            changed = True

    if not changed:
        return False

    meta['question_form_data'] = question_form_data
    config_position.meta_info_data = meta
    config_position.save(update_fields=['meta_info'])
    invalidate_badge_cache_for_position(position)
    return True


def _get_cached_badge_variables(event):
    cached = getattr(event, '_badge_pdf_variables', None)
    if cached is None:
        cached = get_variables(event)
        setattr(event, '_badge_pdf_variables', cached)
    return cached


def get_badge_field_display_values(event, position, layout=None):
    if layout is None:
        layout = get_badge_layout_for_position(event, position)
    if not layout or not layout.allow_customization:
        return {}

    ask_user_keys = set(layout.ask_user_fields_data)
    overrides = get_badge_field_overrides(position)
    variables = _get_cached_badge_variables(event)
    order = position.order
    ev = position.subevent or event
    values = {}

    for field in get_badge_customizable_fields(event, layout):
        key = field['key']
        if key not in ask_user_keys:
            continue
        if key in overrides:
            values[key] = overrides[key]
            continue
        variable = variables.get(key)
        if variable and 'evaluate' in variable:
            try:
                values[key] = str(variable['evaluate'](position, order, ev) or '')
            except Exception:
                values[key] = ''
        else:
            values[key] = str(field.get('sample') or '')
    return values


def get_badge_bundle_root(position):
    return position.addon_to if position.addon_to_id else position


def get_badge_config_position(position):
    return get_badge_bundle_root(position)


def get_badge_bundle_positions(position):
    root = get_badge_bundle_root(position)
    return [root, *list(root.addons.all())]


def get_badge_customizable_fields(event, layout):
    if not layout:
        return []

    if isinstance(layout, BadgeLayout) and hasattr(layout, '_badge_customizable_fields_cache'):
        return layout._badge_customizable_fields_cache

    if isinstance(layout, BadgeLayout):
        layout_data = layout.layout_data
    elif isinstance(layout, str):
        try:
            layout_data = json.loads(layout)
        except ValueError:
            return []
    else:
        layout_data = layout

    if not isinstance(layout_data, list):
        return []

    variables = _get_cached_badge_variables(event)
    fields = []
    seen_keys = set()
    for obj in layout_data:
        if not isinstance(obj, dict) or obj.get('type') not in ('text', 'textarea'):
            continue

        content = normalize_badge_content_key(obj.get('content'))
        if not content or content in ('other', 'other_i18n') or content in seen_keys:
            continue

        variable = variables.get(content, {})
        label = variable.get('label') or _badge_field_fallback_label(content)
        fields.append(
            {
                'key': content,
                'label': str(label),
                'sample': str(variable.get('editor_sample') or obj.get('text') or ''),
            }
        )
        seen_keys.add(content)

    if isinstance(layout, BadgeLayout):
        layout._badge_customizable_fields_cache = fields
    return fields


def get_badge_bundle_option_choices(event, position):
    """
    Return all configurable badge choices for one attendee bundle.

    The bundle is defined as a base position plus all attached add-ons.
    Choices are deduplicated by key while preserving discovery order.

    Includes products that only use the event default layout when that layout
    allows customization with ask-user fields. Explicit no-badge assignments
    (layout=None) are skipped because no layout resolves for them.
    """
    seen_keys = set()
    choices = []
    for bundle_position in get_badge_bundle_positions(position):
        layout = get_badge_layout_for_position(event, bundle_position)
        if not layout or not layout.allow_customization:
            continue

        ask_user_keys = set(layout.ask_user_fields_data)
        for field in get_badge_customizable_fields(event, layout):
            if field['key'] not in ask_user_keys or field['key'] in seen_keys:
                continue
            choices.append(
                (
                    field['key'],
                    field['sample'] if field['key'].startswith('question_') and field.get('sample') else field['label'],
                )
            )
            seen_keys.add(field['key'])
    return choices


def get_badge_visible_field_labels(event, position, hidden_fields=None, layout=None):
    if layout is None:
        layout = get_badge_layout_for_position(event, position)
    if not layout or not layout.allow_customization:
        return []

    ask_user_keys = set(layout.ask_user_fields_data)
    hidden_fields = {
        str(value) for value in (hidden_fields if hidden_fields is not None else get_badge_hidden_fields(position))
    }
    return [
        field['label']
        for field in get_badge_customizable_fields(event, layout)
        if field['key'] in ask_user_keys and field['key'] not in hidden_fields
    ]


def format_badge_option_labels(labels):
    """Format selected badge field labels for order/export display."""
    labels = [str(label) for label in labels]
    if not labels:
        return str(_('No optional badge fields selected'))
    return ', '.join(labels)


def get_badge_options_display(event, position):
    """
    Return a human-readable badge-options summary for order views.

    Uses the same layout resolution as checkout/modify form injection, including
    the event default layout when no product/voucher assignment exists.
    """
    layout = get_badge_layout_for_position(event, position)
    if not layout or not layout.allow_customization or not layout.ask_user_fields_data:
        return None
    return format_badge_option_labels(get_badge_visible_field_labels(event, position, layout=layout))


def append_badge_options_additional_field(event, position, additional_fields, present_keys=None):
    """
    Append a Badge options row for order/cart display when applicable.

    Matches checkout form injection: only the bundle root position shows options,
    and the row is skipped when that form field was already injected.
    Returns True if a field was appended.
    """
    if get_badge_config_position(position) != position:
        return False
    if present_keys is not None and BADGE_HIDDEN_FIELDS_KEY in present_keys:
        return False
    display = get_badge_options_display(event, position)
    if display is None:
        return False
    additional_fields.append(
        {
            'answer': display,
            'question': _('Badge options'),
        }
    )
    return True


def get_badge_visible_field_values(event, position, hidden_fields=None):
    layout = get_badge_layout_for_position(event, position)
    if not layout or not layout.allow_customization:
        return []

    ask_user_keys = set(layout.ask_user_fields_data)
    hidden_fields = {
        str(value) for value in (hidden_fields if hidden_fields is not None else get_badge_hidden_fields(position))
    }

    variables = _get_cached_badge_variables(event)

    values = []
    for field in get_badge_customizable_fields(event, layout):
        if field['key'] in ask_user_keys and field['key'] not in hidden_fields:
            if field['key'] in variables:
                try:
                    val = variables[field['key']]['evaluate'](position, position.order, event)
                    if val:
                        values.append(str(val))
                except (KeyError, ValueError, AttributeError, TypeError):
                    logger.exception('Failed to evaluate badge field')
    return values


def _badge_field_fallback_label(content):
    if content.startswith('question_'):
        return _('Question')
    if content.startswith('meta:'):
        return _('Event meta: {key}').format(key=content[5:])
    if content.startswith('itemmeta:'):
        return _('Product meta: {key}').format(key=content[9:])
    return content.replace('_', ' ').replace(':', ' - ').title()
