import datetime

import pytest
from django.core import mail as djmail
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Checkin,
    Event,
    Product as Item,
    Order,
    OrderPosition,
    Organizer,
    Team,
    User,
)


@pytest.fixture
def event():
    """Returns an event instance"""
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='tests.tickets.testdummy',
    )
    return event


@pytest.fixture
def item(event):
    """Returns an item instance"""
    return Item.objects.create(name='Test item', event=event, default_price=13)


@pytest.fixture
def checkin_list(event):
    """Returns an checkin list instance"""
    return event.checkin_lists.create(name='Test Checkinlist', all_products=True)


@pytest.fixture
def order(item):
    """Returns an order instance"""
    o = Order.objects.create(
        event=item.event,
        status=Order.STATUS_PENDING,
        expires=now() + datetime.timedelta(hours=1),
        total=13,
        code='DUMMY',
        email='dummy@dummy.test',
        datetime=now(),
        locale='en',
    )
    return o


@pytest.fixture
def pos(order, item):
    return OrderPosition.objects.create(order=order, product=item, price=13)


@pytest.fixture
def logged_in_client(client, event):
    """Returns a logged client"""
    user = User.objects.create_superuser('dummy@dummy.dummy', 'dummy')
    t = Team.objects.create(organizer=event.organizer, can_view_orders=True, can_change_orders=True)
    t.members.add(user)
    t.limit_events.add(event)
    client.force_login(user)
    return client


@pytest.fixture
def sendmail_url(event):
    """Returns a url for sendmail"""
    url = '/control/event/{orga}/{event}/sendmail/'.format(
        event=event.slug,
        orga=event.organizer.slug,
    )
    return url


@pytest.mark.django_db
def test_sendmail_view(logged_in_client, sendmail_url, expected=200):
    response = logged_in_client.get(sendmail_url)

    assert response.status_code == expected


@pytest.mark.django_db
def test_sendmail_simple_case(logged_in_client, sendmail_url, event, order, pos):
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.product_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content

    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == [order.email]
    assert djmail.outbox[0].subject == 'Test subject'
    assert 'This is a test file for sending mails.' in djmail.outbox[0].body

    url = sendmail_url + 'history/'
    response = logged_in_client.get(url)

    assert response.status_code == 200
    assert 'Test subject' in response.rendered_content


@pytest.mark.django_db
def test_sendmail_email_not_sent_if_order_not_match(logged_in_client, sendmail_url, event, order, pos):
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'p',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert 'alert-danger' in response.rendered_content

    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_sendmail_preview(logged_in_client, sendmail_url, event, order, pos):
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'action': 'preview',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'E-mail preview' in response.rendered_content

    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_sendmail_invalid_data(logged_in_client, sendmail_url, event, order, pos):
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': 'Test subject',
        },
        follow=True,
    )

    assert 'has-error' in response.rendered_content

    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_sendmail_multi_locales(logged_in_client, sendmail_url, event, item):
    djmail.outbox = []

    event.settings.set('locales', ['en', 'de'])

    with scopes_disabled():
        o = Order.objects.create(
            event=item.event,
            status=Order.STATUS_PAID,
            expires=now() + datetime.timedelta(hours=1),
            total=13,
            code='DUMMY',
            email='dummy@dummy.test',
            datetime=now(),
            locale='de',
        )
        OrderPosition.objects.create(order=o, item=item, price=13)

    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'p',
            'recipients': 'orders',
            'items': item.pk,
            'subject_0': 'Test subject',
            'message_0': 'Test message',
            'subject_1': 'Benutzer',
            'message_1': 'Test nachricht',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content

    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == [o.email]
    assert djmail.outbox[0].subject == 'Benutzer'
    assert 'Test nachricht' in djmail.outbox[0].body

    url = sendmail_url + 'history/'
    response = logged_in_client.get(url)

    assert response.status_code == 200
    assert 'Benutzer' in response.rendered_content
    assert 'Test nachricht' in response.rendered_content


@pytest.mark.django_db
def test_sendmail_subevents(logged_in_client, sendmail_url, event, order, pos):
    event.has_subevents = True
    event.save()
    with scopes_disabled():
        se1 = event.subevents.create(name='Subevent FOO', date_from=now())
        se2 = event.subevents.create(name='Bar', date_from=now())
        op = order.positions.last()
    op.subevent = se1
    op.save()

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'subevent': se1.pk,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'subevent': se2.pk,
        },
        follow=True,
    )
    assert len(djmail.outbox) == 0

    url = sendmail_url + 'history/'
    response = logged_in_client.get(url)

    assert response.status_code == 200
    assert 'Subevent FOO' in response.rendered_content


@pytest.mark.django_db
def test_sendmail_placeholder(logged_in_client, sendmail_url, event, order, pos):
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': '{code} Test subject',
            'message_0': 'This is a test file for sending mails.',
            'action': 'preview',
        },
        follow=True,
    )

    assert response.status_code == 200
    assert 'F8VVL' in response.rendered_content

    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_sendmail_attendee_mails(logged_in_client, sendmail_url, event, order, pos):
    p = pos
    event.settings.attendee_emails_asked = True
    p.attendee_email = 'attendee@dummy.test'
    p.save()

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['attendee@dummy.test']
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body


@pytest.mark.django_db
def test_sendmail_both_mails(logged_in_client, sendmail_url, event, order, pos):
    p = pos
    event.settings.attendee_emails_asked = True
    p.attendee_email = 'attendee@dummy.test'
    p.save()

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'both',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 2
    assert djmail.outbox[0].to == ['attendee@dummy.test']
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body
    assert djmail.outbox[1].to == ['dummy@dummy.test']
    assert '/ticket/' not in djmail.outbox[1].body
    assert '/order/' in djmail.outbox[1].body


@pytest.mark.django_db
def test_sendmail_both_but_same_address(logged_in_client, sendmail_url, event, order, pos):
    p = pos
    event.settings.attendee_emails_asked = True
    p.attendee_email = 'dummy@dummy.test'
    p.save()

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'both',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['dummy@dummy.test']
    assert '/ticket/' not in djmail.outbox[0].body
    assert '/order/' in djmail.outbox[0].body


@pytest.mark.django_db
def test_sendmail_attendee_fallback(logged_in_client, sendmail_url, event, order, pos):
    p = pos
    event.settings.attendee_emails_asked = True
    p.attendee_email = None
    p.save()

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['dummy@dummy.test']
    assert '/ticket/' not in djmail.outbox[0].body
    assert '/order/' in djmail.outbox[0].body


@pytest.mark.django_db
def test_sendmail_attendee_product_filter(logged_in_client, sendmail_url, event, order, pos):
    event.settings.attendee_emails_asked = True
    with scopes_disabled():
        i2 = Item.objects.create(name='Test item', event=event, default_price=13)
        p = pos
        p.attendee_email = 'attendee1@dummy.test'
        p.save()
        order.positions.create(item=i2, price=0, attendee_email='attendee2@dummy.test')

        djmail.outbox = []
        response = logged_in_client.post(
            sendmail_url,
            {
                'sendto': 'na',
                'recipients': 'attendees',
                'items': i2.pk,
                'subject_0': 'Test subject',
                'message_0': 'This is a test file for sending mails.',
            },
            follow=True,
        )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['attendee2@dummy.test']
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body


@pytest.mark.django_db
def test_sendmail_attendee_checkin_filter(logged_in_client, sendmail_url, event, order, checkin_list, item, pos):
    event.settings.attendee_emails_asked = True
    with scopes_disabled():
        chkl2 = event.checkin_lists.create(name='Test Checkinlist 2', all_products=True)
        p = pos
        p.attendee_email = 'attendee1@dummy.test'
        p.save()
        pos2 = order.positions.create(item=item, price=0, attendee_email='attendee2@dummy.test')
        Checkin.objects.create(position=pos2, list=chkl2)

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos2.item_id,
            'filter_checkins': 'on',
            'checkin_lists': [chkl2.id],
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['attendee2@dummy.test']
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos2.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'filter_checkins': 'on',
            'not_checked_in': 'on',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['attendee1@dummy.test']
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos2.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'filter_checkins': 'on',
            'checkin_lists': [chkl2.id],
            'not_checked_in': 'on',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 2
    assert djmail.outbox[0].to == ['attendee1@dummy.test']
    assert djmail.outbox[1].to == ['attendee2@dummy.test']

    # Test that filtering is ignored if filter_checkins is not set
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos2.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'not_checked_in': 'on',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 2
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body
    assert '/ticket/' in djmail.outbox[1].body
    assert '/order/' not in djmail.outbox[1].body
    to_emails = set(*zip(*[mail.to for mail in djmail.outbox]))
    assert to_emails == {'attendee1@dummy.test', 'attendee2@dummy.test'}

    # Test that filtering is ignored if filter_checkins is not set
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos2.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'checkin_lists': [chkl2.id],
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 2
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body
    assert '/ticket/' in djmail.outbox[1].body
    assert '/order/' not in djmail.outbox[1].body
    to_emails = set(*zip(*[mail.to for mail in djmail.outbox]))
    assert to_emails == {'attendee1@dummy.test', 'attendee2@dummy.test'}

@pytest.mark.django_db
def test_sendmail_save_draft(logged_in_client, sendmail_url, event, order, pos):
    from eventyay.plugins.sendmail.models import EmailQueue
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'order_status': 'na',
            'recipients': 'orders',
            'products': [pos.product_id],
            'subject_0': 'Test draft subject',
            'text_0': 'This is a test draft message.',
            'action': 'draft',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content

    assert len(djmail.outbox) == 0

    drafts = EmailQueue.objects.filter(event=event, is_draft=True)
    assert drafts.count() == 1
    draft = drafts.first()
    assert draft.subject == 'Test draft subject'
    assert 'This is a test draft message.' in str(draft.message)

    with scopes_disabled():
        assert draft.send() is False
    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_edit_draft_without_filters_redirects_to_composer(logged_in_client, event):
    from eventyay.plugins.sendmail.models import EmailQueue

    draft = EmailQueue.objects.create(
        event=event,
        composing_for='attendees',
        subject='Draft without filters',
        message='Message',
        is_draft=True,
    )
    edit_url = reverse(
        'control:event.mail.edit',
        kwargs={
            'organizer': event.organizer.slug,
            'event': event.slug,
            'pk': draft.pk,
        },
    )

    response = logged_in_client.get(edit_url)

    assert response.status_code == 302
    assert response.url.endswith(draft.get_edit_url())


@pytest.fixture
def custom_template(event):
    from eventyay.base.i18n import LazyI18nString
    from eventyay.plugins.sendmail.models import TicketMailTemplate

    return TicketMailTemplate.objects.create(
        event=event,
        subject=LazyI18nString({'en': 'Hello {event}'}),
        text=LazyI18nString({'en': 'Dear customer, welcome to {event}.'}),
        reply_to='reply@example.com',
        bcc='bcc@example.com',
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_custom_template_create(logged_in_client, event):
    from eventyay.plugins.sendmail.models import TicketMailTemplate

    url = reverse(
        'control:event.mail.custom_templates.create',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = logged_in_client.get(url)
    assert response.status_code == 200

    response = logged_in_client.post(
        url,
        {
            'subject_0': 'Custom subject {event}',
            'text_0': 'Custom body for {event}',
            'reply_to': 'hello@example.com',
            'bcc': '',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert TicketMailTemplate.objects.filter(event=event).count() == 1
    template = TicketMailTemplate.objects.get(event=event)
    assert 'Custom subject' in str(template.subject)
    assert 'Custom body' in str(template.text)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_custom_template_compose_prefill(logged_in_client, event, custom_template):
    url = reverse(
        'control:event.mail.send',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = logged_in_client.get(f'{url}?template={custom_template.pk}')
    assert response.status_code == 200
    form = response.context['form']
    assert 'Hello' in str(form.initial.get('subject'))
    assert 'welcome' in str(form.initial.get('text'))
    assert form.initial.get('reply_to') == 'reply@example.com'
    assert form.initial.get('bcc') == 'bcc@example.com'


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_custom_template_delete(logged_in_client, event, custom_template):
    from eventyay.plugins.sendmail.models import TicketMailTemplate

    url = reverse(
        'control:event.mail.custom_templates.delete',
        kwargs={
            'organizer': event.organizer.slug,
            'event': event.slug,
            'pk': custom_template.pk,
        },
    )
    response = logged_in_client.get(url)
    assert response.status_code == 200

    response = logged_in_client.post(url, follow=True)
    assert response.status_code == 200
    assert not TicketMailTemplate.objects.filter(pk=custom_template.pk).exists()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_templates_page_lists_custom_templates(logged_in_client, event, custom_template):
    url = reverse(
        'control:event.mail.templates',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = logged_in_client.get(url)
    assert response.status_code == 200
    assert 'Hello' in response.rendered_content
    assert 'New custom template' in response.rendered_content
    assert 'Custom Mail' in response.rendered_content
    assert 'Placed order' in response.rendered_content


@pytest.mark.django_db
def test_ticket_mail_template_form_validates_reply_to_and_bcc(event):
    from eventyay.plugins.sendmail.forms import TicketMailTemplateForm

    invalid = TicketMailTemplateForm(
        data={
            'subject_0': 'Subject',
            'text_0': 'Body',
            'reply_to': 'not-an-email',
            'bcc': 'ok@example.com, bad-address',
        },
        event=event,
    )
    assert not invalid.is_valid()
    assert 'reply_to' in invalid.errors
    assert 'bcc' in invalid.errors

    valid = TicketMailTemplateForm(
        data={
            'subject_0': 'Subject',
            'text_0': 'Body',
            'reply_to': 'hello@example.com',
            'bcc': 'a@example.com, b@example.com',
        },
        event=event,
    )
    assert valid.is_valid(), valid.errors
    assert valid.cleaned_data['bcc'] == 'a@example.com, b@example.com'
