import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import Order


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL="https://testserver")
def test_organizer_dashboard_onboarding_state(organizer_client, organizer):
    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    response = organizer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    ctx = response.context

    assert ctx['is_onboarding'] is True
    assert 'Getting started' in content or 'getting started' in content.lower()
    assert 'At a glance' in content
    assert 'Event portfolio' in content
    assert 'Organizer tools' in content
    assert 'od-dashboard' in content
    assert ctx['kpi_cards']
    assert len(ctx['kpi_cards']) == 8
    assert ctx['getting_started']


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL="https://testserver")
def test_organizer_dashboard_data_rich_state(organizer_client, organizer, event, team):
    with scopes_disabled():
        event.live = True
        event.date_from = timezone.now()
        event.save()
        Order.objects.create(
            event=event,
            code='DASH1',
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            total=25.0,
            locale='en',
        )
        team.can_view_orders = True
        team.save()

    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    response = organizer_client.get(url + '?refresh=1')
    assert response.status_code == 200
    content = response.content.decode()
    ctx = response.context

    assert ctx['is_onboarding'] is False
    assert ctx['portfolio_events']
    assert 'Event portfolio' in content
    assert str(event.name) in content
    assert 'Create event' in content or 'od-btn-primary' in content
