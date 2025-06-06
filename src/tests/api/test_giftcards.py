import copy
from decimal import Decimal

import pytest
from django_scopes import scopes_disabled

from pretix.base.models import GiftCard, Organizer


@pytest.fixture
def giftcard(organizer, event):
    gc = organizer.issued_gift_cards.create(secret='ABCDEF', currency='EUR')
    gc.transactions.create(value=Decimal('23.00'))
    return gc


@pytest.fixture
def other_giftcard(organizer, event):
    o = Organizer.objects.create(name='Dummy2', slug='dummy2')
    organizer.gift_card_issuer_acceptance.create(issuer=o)
    gc = o.issued_gift_cards.create(secret='GHIJK', currency='EUR')
    return gc


TEST_GC_RES = {
    'id': 1,
    'secret': 'ABCDEF',
    'value': '23.00',
    'testmode': False,
    'expires': None,
    'conditions': None,
    'currency': 'EUR',
}


@pytest.mark.django_db
def test_giftcard_list(token_client, organizer, event, giftcard, other_giftcard):
    res = dict(TEST_GC_RES)
    res['id'] = giftcard.pk
    res['issuance'] = giftcard.issuance.isoformat().replace('+00:00', 'Z')

    resp = token_client.get('/api/v1/organizers/{}/giftcards/'.format(organizer.slug))
    assert resp.status_code == 200
    assert [res] == resp.data['results']

    resp = token_client.get('/api/v1/organizers/{}/giftcards/?testmode=true'.format(organizer.slug))
    assert resp.status_code == 200
    assert [] == resp.data['results']
    resp = token_client.get('/api/v1/organizers/{}/giftcards/?testmode=false'.format(organizer.slug))
    assert resp.status_code == 200
    assert [res] == resp.data['results']

    resp = token_client.get('/api/v1/organizers/{}/giftcards/?secret=DEF'.format(organizer.slug))
    assert resp.status_code == 200
    assert [] == resp.data['results']
    resp = token_client.get('/api/v1/organizers/{}/giftcards/?secret=ABCDEF'.format(organizer.slug))
    assert resp.status_code == 200
    assert [res] == resp.data['results']

    resp = token_client.get('/api/v1/organizers/{}/giftcards/?include_accepted=true'.format(organizer.slug))
    assert resp.status_code == 200
    assert 2 == len(resp.data['results'])


@pytest.mark.django_db
def test_giftcard_detail(token_client, organizer, event, giftcard):
    res = dict(TEST_GC_RES)
    res['id'] = giftcard.pk
    res['issuance'] = giftcard.issuance.isoformat().replace('+00:00', 'Z')
    resp = token_client.get('/api/v1/organizers/{}/giftcards/{}/'.format(organizer.slug, giftcard.pk))
    assert resp.status_code == 200
    assert res == resp.data


TEST_GIFTCARD_CREATE_PAYLOAD = {
    'secret': 'DEFABC',
    'value': '12.00',
    'testmode': False,
    'currency': 'EUR',
}


@pytest.mark.django_db
def test_giftcard_create(token_client, organizer, event):
    resp = token_client.post(
        '/api/v1/organizers/{}/giftcards/'.format(organizer.slug),
        TEST_GIFTCARD_CREATE_PAYLOAD,
        format='json',
    )
    assert resp.status_code == 201
    with scopes_disabled():
        gc = GiftCard.objects.get(pk=resp.data['id'])
        assert gc.issuer == organizer
        assert gc.value == Decimal('12.00')


@pytest.mark.django_db
def test_giftcard_duplicate_secert(token_client, organizer, event, giftcard):
    res = copy.copy(TEST_GIFTCARD_CREATE_PAYLOAD)
    res['secret'] = 'ABCDEF'
    resp = token_client.post('/api/v1/organizers/{}/giftcards/'.format(organizer.slug), res, format='json')
    assert resp.status_code == 400
    assert resp.data == {
        'secret': ['A gift card with the same secret already exists in your or an affiliated organizer account.']
    }


@pytest.mark.django_db
def test_giftcard_patch(token_client, organizer, event, giftcard):
    resp = token_client.patch(
        '/api/v1/organizers/{}/giftcards/{}/'.format(organizer.slug, giftcard.pk),
        {'secret': 'foo', 'value': '10.00', 'testmode': True, 'currency': 'USD'},
        format='json',
    )
    assert resp.status_code == 200
    giftcard.refresh_from_db()
    assert giftcard.value == Decimal('10.00')
    assert giftcard.secret == 'ABCDEF'
    assert giftcard.currency == 'EUR'
    assert not giftcard.testmode


@pytest.mark.django_db
def test_giftcard_patch_min_value(token_client, organizer, event, giftcard):
    resp = token_client.patch(
        '/api/v1/organizers/{}/giftcards/{}/'.format(organizer.slug, giftcard.pk),
        {
            'value': '-10.00',
        },
        format='json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_giftcard_transact(token_client, organizer, event, giftcard):
    resp = token_client.post(
        '/api/v1/organizers/{}/giftcards/{}/transact/'.format(organizer.slug, giftcard.pk),
        {
            'value': '10.00',
        },
        format='json',
    )
    assert resp.status_code == 200
    giftcard.refresh_from_db()
    assert giftcard.value == Decimal('33.00')
    resp = token_client.post(
        '/api/v1/organizers/{}/giftcards/{}/transact/'.format(organizer.slug, giftcard.pk),
        {'value': '10.00', 'text': 'bla'},
        format='json',
    )
    assert resp.status_code == 200
    giftcard.refresh_from_db()
    assert giftcard.value == Decimal('43.00')
    assert giftcard.transactions.last().text == 'bla'


@pytest.mark.django_db
def test_giftcard_transact_min_zero(token_client, organizer, event, giftcard):
    resp = token_client.post(
        '/api/v1/organizers/{}/giftcards/{}/transact/'.format(organizer.slug, giftcard.pk),
        {
            'value': '-100.00',
        },
        format='json',
    )
    assert resp.status_code == 409
    assert resp.data == {'value': ['The gift card does not have sufficient credit for this operation.']}
    giftcard.refresh_from_db()
    assert giftcard.value == Decimal('23.00')


@pytest.mark.django_db
def test_giftcard_no_deletion(token_client, organizer, event, giftcard):
    resp = token_client.delete(
        '/api/v1/organizers/{}/giftcards/{}/'.format(organizer.slug, giftcard.pk),
    )
    assert resp.status_code == 405


@pytest.mark.django_db
def test_giftcard_transactions(token_client, organizer, giftcard):
    resp = token_client.get(
        '/api/v1/organizers/{}/giftcards/{}/transactions/'.format(organizer.slug, giftcard.pk),
    )
    assert resp.status_code == 200
    assert resp.data == {
        'count': 1,
        'next': None,
        'previous': None,
        'results': [
            {
                'id': giftcard.transactions.first().pk,
                'datetime': giftcard.transactions.first().datetime.isoformat().replace('+00:00', 'Z'),
                'value': '23.00',
                'event': None,
                'order': None,
                'text': None,
            }
        ],
    }
