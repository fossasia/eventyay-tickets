import pytest
from django.urls import resolve
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, Team, User
from eventyay.control.navigation import get_admin_navigation, get_event_navigation


@pytest.fixture
def organizer():
    return Organizer.objects.create(name='Dummy', slug='dummy')


@pytest.fixture
def event(organizer):
    return Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now(),
    )


def _nav_includes_vouchers(nav) -> bool:
    for item in nav:
        if 'vouchers' in item.get('url', ''):
            return True
        for child in item.get('children', []):
            if 'vouchers' in child.get('url', ''):
                return True
    return False


def _find_products_nav(nav):
    for item in nav:
        if str(item.get('label')) == 'Products':
            return item
    return None


def _find_orders_nav(nav):
    for item in nav:
        if str(item.get('label')) == 'Orders':
            return item
    return None


@pytest.mark.django_db
def test_voucher_only_navigation_shows_vouchers(event, rf):
    user = User.objects.create_user('voucher@example.com', 'dummy')
    team = Team.objects.create(organizer=event.organizer, can_view_vouchers=True, all_events=True)
    team.members.add(user)

    request = rf.get(f'/control/event/{event.organizer.slug}/{event.slug}/')
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.eventpermset = user.get_event_permission_set(event.organizer, event)
    request.resolver_match = resolve(
        f'/control/event/{event.organizer.slug}/{event.slug}/'
    )

    nav = get_event_navigation(request)

    assert _nav_includes_vouchers(nav)
    assert _find_products_nav(nav) is None


@pytest.mark.django_db
def test_product_and_voucher_navigation_keeps_vouchers_under_products(event, rf):
    user = User.objects.create_user('products@example.com', 'dummy')
    team = Team.objects.create(
        organizer=event.organizer,
        can_change_items=True,
        can_view_vouchers=True,
        all_events=True,
    )
    team.members.add(user)

    request = rf.get(f'/control/event/{event.organizer.slug}/{event.slug}/')
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.eventpermset = user.get_event_permission_set(event.organizer, event)
    request.resolver_match = resolve(
        f'/control/event/{event.organizer.slug}/{event.slug}/'
    )

    nav = get_event_navigation(request)

    products = _find_products_nav(nav)
    assert products is not None
    assert _nav_includes_vouchers([products])
    assert not any(str(item.get('label')) == 'Vouchers' for item in nav)


@pytest.mark.django_db
def test_orders_parent_nav_links_to_overview(event, rf):
    user = User.objects.create_user('orders@example.com', 'dummy')
    team = Team.objects.create(
        organizer=event.organizer,
        can_view_orders=True,
        all_events=True,
    )
    team.members.add(user)

    request = rf.get(f'/control/event/{event.organizer.slug}/{event.slug}/')
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.eventpermset = user.get_event_permission_set(event.organizer, event)
    request.resolver_match = resolve(
        f'/control/event/{event.organizer.slug}/{event.slug}/'
    )

    nav = get_event_navigation(request)
    orders = _find_orders_nav(nav)

    assert orders is not None
    assert orders['url'].endswith('/orders/overview/')
    assert any(str(child.get('label')) == 'Overview' for child in orders.get('children', []))


@pytest.mark.django_db
def test_banktransfer_only_navigation_shows_import_export(event, rf):
    event.plugins = 'eventyay.plugins.banktransfer'
    event.save()
    user = User.objects.create_user('bank@example.com', 'dummy')
    team = Team.objects.create(
        organizer=event.organizer,
        can_manage_bank_transfers=True,
        all_events=True,
    )
    team.members.add(user)

    request = rf.get(f'/control/event/{event.organizer.slug}/{event.slug}/')
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.eventpermset = user.get_event_permission_set(event.organizer, event)
    request.resolver_match = resolve(
        f'/control/event/{event.organizer.slug}/{event.slug}/'
    )

    nav = get_event_navigation(request)
    orders_nav = None
    for item in nav:
        if str(item.get('label')) == 'Orders':
            orders_nav = item
            break

    assert orders_nav is not None
    assert any(str(child.get('label')) == 'Import / Export' for child in orders_nav.get('children', []))
    assert not any(str(child.get('label')) == 'Overview' for child in orders_nav.get('children', []))
    assert not any(str(child.get('label')) == 'All orders' for child in orders_nav.get('children', []))


@pytest.mark.django_db
def test_admin_navigation_structure_and_hierarchy(rf):
    user = User.objects.create_user('admin@example.com', 'dummy', is_staff=True)
    request = rf.get('/admin/global/settings/')
    request.user = user
    request.resolver_match = resolve('/admin/global/settings/')

    nav = get_admin_navigation(request)
    labels = [str(item.get('label')) for item in nav]

    assert labels == [
        'Global settings',
        'Business',
        'Task management',
        'Video',
        'Platform Data',
        'Users',
    ]

    # Vouchers is no longer a standalone top-level sidebar item
    assert 'Vouchers' not in labels

    # Check Business subitems
    business_nav = next(item for item in nav if str(item.get('label')) == 'Business')
    assert business_nav.get('icon') == 'briefcase'
    assert 'children' in business_nav

    business_children_labels = [str(c.get('label')) for c in business_nav['children']]
    assert business_children_labels == ['Business Settings', 'Event vouchers']

    # Check URLs of Business children
    business_settings = next(c for c in business_nav['children'] if str(c.get('label')) == 'Business Settings')
    assert business_settings['url'] == '/admin/global/business/'

    event_vouchers = next(c for c in business_nav['children'] if str(c.get('label')) == 'Event vouchers')
    assert event_vouchers['url'] == '/admin/vouchers/'


@pytest.mark.django_db
def test_admin_navigation_voucher_active_state(rf):
    user = User.objects.create_user('admin@example.com', 'dummy', is_staff=True)
    request = rf.get('/admin/vouchers/')
    request.user = user
    request.resolver_match = resolve('/admin/vouchers/')

    nav = get_admin_navigation(request)
    business_nav = next(item for item in nav if str(item.get('label')) == 'Business')
    assert business_nav['active'] is True

    event_vouchers = next(c for c in business_nav['children'] if str(c.get('label')) == 'Event vouchers')
    assert event_vouchers['active'] is True

    business_settings = next(c for c in business_nav['children'] if str(c.get('label')) == 'Business Settings')
    assert business_settings['active'] is False


@pytest.mark.django_db
def test_admin_navigation_global_settings_children(rf):
    user = User.objects.create_user('admin@example.com', 'dummy', is_staff=True)
    request = rf.get('/admin/global/settings/')
    request.user = user
    request.resolver_match = resolve('/admin/global/settings/')

    nav = get_admin_navigation(request)
    global_nav = next(item for item in nav if str(item.get('label')) == 'Global settings')
    assert global_nav['active'] is True

    children_labels = [str(c.get('label')) for c in global_nav['children']]
    assert children_labels == [
        'Settings',
        'Ticketing',
        'System information',
        'Pages',
        'Generate keys for SSO',
        'Social login settings',
        'Plugins',
    ]

    # Meta data and Update check are removed as separate sidebar items
    assert 'Meta data' not in children_labels
    assert 'Update check' not in children_labels

    # Check URLs of Settings and Ticketing children
    settings_item = next(c for c in global_nav['children'] if str(c.get('label')) == 'Settings')
    assert settings_item['url'] == '/admin/global/settings/'
    assert settings_item['active'] is True

    ticketing_item = next(c for c in global_nav['children'] if str(c.get('label')) == 'Ticketing')
    assert ticketing_item['url'] == '/admin/global/ticketing/'
    assert ticketing_item['active'] is False


@pytest.mark.django_db
def test_admin_navigation_ticketing_active_state(rf):
    user = User.objects.create_user('admin@example.com', 'dummy', is_staff=True)
    request = rf.get('/admin/global/ticketing/')
    request.user = user
    request.resolver_match = resolve('/admin/global/ticketing/')

    nav = get_admin_navigation(request)
    global_nav = next(item for item in nav if str(item.get('label')) == 'Global settings')
    assert global_nav['active'] is True

    ticketing_item = next(c for c in global_nav['children'] if str(c.get('label')) == 'Ticketing')
    assert ticketing_item['active'] is True

    settings_item = next(c for c in global_nav['children'] if str(c.get('label')) == 'Settings')
    assert settings_item['active'] is False
