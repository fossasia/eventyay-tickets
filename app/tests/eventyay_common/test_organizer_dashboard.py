import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order, OrderPayment


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


@pytest.mark.django_db
@override_settings(EVENTYAY_OBLIGATORY_2FA=False, SITE_URL="https://testserver")
def test_organizer_dashboard_revenue_currency_filter(organizer_client, organizer, event, team):
    with scopes_disabled():
        event.live = True
        event.currency = 'USD'
        event.date_from = timezone.now()
        event.save()
        event_inr = Event.objects.create(
            organizer=organizer,
            name='INR Event',
            slug='inr-event',
            live=True,
            currency='INR',
            date_from=timezone.now(),
        )
        team.can_view_orders = True
        team.all_events = True
        team.save()

        order_usd = Order.objects.create(
            event=event,
            code='CURUSD',
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            total=100,
            locale='en',
        )
        OrderPayment.objects.create(
            order=order_usd,
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=100,
            provider='manual',
            payment_date=timezone.now(),
        )
        order_inr = Order.objects.create(
            event=event_inr,
            code='CURINR',
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            total=750,
            locale='en',
        )
        OrderPayment.objects.create(
            order=order_inr,
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=750,
            provider='manual',
            payment_date=timezone.now(),
        )

    url = reverse('eventyay_common:organizer.dashboard', kwargs={'organizer': organizer.slug})
    response = organizer_client.get(url + '?refresh=1')
    assert response.status_code == 200
    content = response.content.decode()
    ctx = response.context

    assert 'data-od-revenue-filter' in content
    assert 'od-revenue-currency' in content
    assert 'data-od-auto-submit' not in content
    revenue_card = next(card for card in ctx['kpi_cards'] if card.get('currencies'))
    assert set(revenue_card['currencies']) == {'USD', 'INR'}
    assert len(revenue_card['revenue_options']) == 2

    filtered = organizer_client.get(url + '?revenue_currency=INR&refresh=1')
    assert filtered.status_code == 200
    filtered_content = filtered.content.decode()
    assert 'data-od-revenue-filter' in filtered_content
    assert '>Apply<' not in filtered_content
    filtered_card = next(
        card for card in filtered.context['kpi_cards'] if card.get('currencies')
    )
    assert filtered_card['selected_currency'] == 'INR'
    assert filtered_card['value_is_money'] is True
    assert filtered.context['selected_revenue_currency'] == 'INR'
    # Full list stays in the DOM for client-side filtering
    assert len(filtered.context['top_events']) >= 2
    assert {row['currency'] for row in filtered.context['top_events']} >= {'USD', 'INR'}
