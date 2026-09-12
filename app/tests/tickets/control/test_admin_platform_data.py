import datetime
from decimal import Decimal

from bs4 import BeautifulSoup
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Event,
    Order,
    OrderPosition,
    Organizer,
    Submission,
    SubmissionType,
    User,
)
from tests.tickets.base import SoupTest


@override_settings(SITE_URL='https://testserver')
class AdminPlatformDataEventLinksTest(SoupTest):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user('admin@example.com', 'dummy', is_staff=True)
        self.client.force_login(self.admin)
        self.admin.staffsession_set.create(date_start=now(), session_key=self.client.session.session_key)

        self.orga1 = Organizer.objects.create(name='CCC', slug='ccc')
        self.orga2 = Organizer.objects.create(name='MRM', slug='mrm')

        self.event1 = Event.objects.create(
            organizer=self.orga1,
            name='30C3',
            slug='30c3',
            live=True,
            date_from=datetime.datetime(2026, 12, 26, tzinfo=datetime.UTC),
        )
        self.event2 = Event.objects.create(
            organizer=self.orga2,
            name='MRMCD14',
            slug='mrmcd14',
            live=True,
            date_from=datetime.datetime(2026, 9, 1, tzinfo=datetime.UTC),
        )

        self.item1 = self.event1.products.create(name='Ticket 1', default_price=Decimal('10.00'))
        self.item2 = self.event2.products.create(name='Ticket 2', default_price=Decimal('20.00'))

        self.order1 = Order.objects.create(
            code='ORD01',
            event=self.event1,
            email='alice@example.com',
            status=Order.STATUS_PAID,
            datetime=now(),
            total=Decimal('10.00'),
        )
        self.order2 = Order.objects.create(
            code='ORD02',
            event=self.event2,
            email='bob@example.com',
            status=Order.STATUS_PAID,
            datetime=now(),
            total=Decimal('20.00'),
        )

        self.pos1 = OrderPosition.objects.create(
            order=self.order1,
            product=self.item1,
            attendee_name_cached='Alice Smith',
            attendee_email='alice@example.com',
            price=Decimal('10.00'),
        )
        self.pos2 = OrderPosition.objects.create(
            order=self.order2,
            product=self.item2,
            attendee_name_cached='Bob Jones',
            attendee_email='bob@example.com',
            price=Decimal('20.00'),
        )

        self.sub_type1 = SubmissionType.objects.create(event=self.event1, name='Talk')
        self.sub_type2 = SubmissionType.objects.create(event=self.event2, name='Workshop')

        self.sub1 = Submission.objects.create(
            title='Opening Keynote',
            event=self.event1,
            submission_type=self.sub_type1,
            state='submitted',
        )
        self.sub2 = Submission.objects.create(
            title='Advanced Hacking Workshop',
            event=self.event2,
            submission_type=self.sub_type2,
            state='accepted',
        )

    def test_attendees_event_name_links_to_common_dashboard(self):
        expected_href1 = reverse(
            'eventyay_common:event.index', kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug}
        )
        expected_href2 = reverse(
            'eventyay_common:event.index', kwargs={'organizer': self.orga2.slug, 'event': self.event2.slug}
        )
        self.assertEqual(expected_href1, '/common/event/ccc/30c3/')
        self.assertEqual(expected_href2, '/common/event/mrm/mrmcd14/')

        test_cases = (
            ('/admin/attendees/', '30C3', expected_href1, True),
            ('/admin/attendees/', 'MRMCD14', expected_href2, True),
            ('/admin/attendees/?query=Alice', '30C3', expected_href1, True),
            ('/admin/attendees/?query=Alice', 'MRMCD14', expected_href2, False),
            ('/admin/attendees/?event_query=30C3', '30C3', expected_href1, True),
            ('/admin/attendees/?event_query=30C3', 'MRMCD14', expected_href2, False),
            ('/admin/attendees/?event_query=mrmcd14', 'MRMCD14', expected_href2, True),
            ('/admin/attendees/?event_query=mrmcd14', '30C3', expected_href1, False),
            ('/admin/attendees/?ordering=event', '30C3', expected_href1, True),
            ('/admin/attendees/?ordering=-event', '30C3', expected_href1, True),
        )

        for url, event_name, expected_href, should_exist in test_cases:
            with self.subTest(url=url, event_name=event_name):
                resp = self.client.get(url, follow=True)
                self.assertEqual(resp.status_code, 200)

                doc = BeautifulSoup(resp.content, 'html.parser')
                matching_links = [
                    link for link in doc.select('a')
                    if link.get_text(strip=True) == event_name
                ]

                if should_exist:
                    self.assertTrue(len(matching_links) > 0)
                    self.assertEqual(matching_links[0]['href'], expected_href)
                else:
                    self.assertEqual(len(matching_links), 0)

        # Ensure ticket-specific order link is preserved and not changed
        resp = self.client.get('/admin/attendees/', follow=True)
        doc = BeautifulSoup(resp.content, 'html.parser')
        order_link = next(link for link in doc.select('a') if link.get_text(strip=True) == 'ORD01')
        self.assertEqual(
            order_link['href'],
            reverse(
                'control:event.order',
                kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug, 'code': self.order1.code},
            ),
        )

    def test_orders_event_name_links_to_common_dashboard(self):
        expected_href1 = reverse(
            'eventyay_common:event.index', kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug}
        )
        expected_href2 = reverse(
            'eventyay_common:event.index', kwargs={'organizer': self.orga2.slug, 'event': self.event2.slug}
        )
        self.assertEqual(expected_href1, '/common/event/ccc/30c3/')
        self.assertEqual(expected_href2, '/common/event/mrm/mrmcd14/')

        test_cases = (
            ('/admin/orders/', '30C3', expected_href1, True),
            ('/admin/orders/', 'MRMCD14', expected_href2, True),
            ('/admin/orders/?query=ORD01', '30C3', expected_href1, True),
            ('/admin/orders/?query=ORD01', 'MRMCD14', expected_href2, False),
            ('/admin/orders/?query=bob@example.com', 'MRMCD14', expected_href2, True),
            ('/admin/orders/?query=bob@example.com', '30C3', expected_href1, False),
            ('/admin/orders/?status=p', '30C3', expected_href1, True),
            ('/admin/orders/?ordering=event', '30C3', expected_href1, True),
            ('/admin/orders/?ordering=-event', '30C3', expected_href1, True),
        )

        for url, event_name, expected_href, should_exist in test_cases:
            with self.subTest(url=url, event_name=event_name):
                resp = self.client.get(url, follow=True)
                self.assertEqual(resp.status_code, 200)

                doc = BeautifulSoup(resp.content, 'html.parser')
                matching_links = [
                    link for link in doc.select('a')
                    if link.get_text(strip=True) == event_name
                ]

                if should_exist:
                    self.assertTrue(len(matching_links) > 0)
                    self.assertEqual(matching_links[0]['href'], expected_href)
                else:
                    self.assertEqual(len(matching_links), 0)

        # Ensure ticket-specific order link and organizer link are preserved
        resp = self.client.get('/admin/orders/', follow=True)
        doc = BeautifulSoup(resp.content, 'html.parser')
        order_link = next(link for link in doc.select('a') if link.get_text(strip=True) == 'ORD01')
        self.assertEqual(
            order_link['href'],
            reverse(
                'control:event.order',
                kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug, 'code': self.order1.code},
            ),
        )
        orga_link = next(link for link in doc.select('a') if link.get_text(strip=True) == 'CCC')
        self.assertEqual(
            orga_link['href'],
            reverse('eventyay_common:organizer.events', kwargs={'organizer': self.orga1.slug}),
        )

    def test_submissions_event_name_links_to_common_dashboard(self):
        expected_href1 = reverse(
            'eventyay_common:event.index', kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug}
        )
        expected_href2 = reverse(
            'eventyay_common:event.index', kwargs={'organizer': self.orga2.slug, 'event': self.event2.slug}
        )
        self.assertEqual(expected_href1, '/common/event/ccc/30c3/')
        self.assertEqual(expected_href2, '/common/event/mrm/mrmcd14/')

        test_cases = (
            ('/admin/submissions/', '30C3', expected_href1, True),
            ('/admin/submissions/', 'MRMCD14', expected_href2, True),
            ('/admin/submissions/?query=Keynote', '30C3', expected_href1, True),
            ('/admin/submissions/?query=Keynote', 'MRMCD14', expected_href2, False),
            ('/admin/submissions/?event_query=30c3', '30C3', expected_href1, True),
            ('/admin/submissions/?event_query=30c3', 'MRMCD14', expected_href2, False),
            ('/admin/submissions/?proposal_state=accepted', 'MRMCD14', expected_href2, True),
            ('/admin/submissions/?proposal_state=accepted', '30C3', expected_href1, False),
            ('/admin/submissions/?ordering=event', '30C3', expected_href1, True),
            ('/admin/submissions/?ordering=-event', '30C3', expected_href1, True),
        )

        for url, event_name, expected_href, should_exist in test_cases:
            with self.subTest(url=url, event_name=event_name):
                resp = self.client.get(url, follow=True)
                self.assertEqual(resp.status_code, 200)

                doc = BeautifulSoup(resp.content, 'html.parser')
                matching_links = [
                    link for link in doc.select('a')
                    if link.get_text(strip=True) == event_name
                ]

                if should_exist:
                    self.assertTrue(len(matching_links) > 0)
                    self.assertEqual(matching_links[0]['href'], expected_href)
                else:
                    self.assertEqual(len(matching_links), 0)

        # Ensure submission-specific link is preserved
        resp = self.client.get('/admin/submissions/', follow=True)
        doc = BeautifulSoup(resp.content, 'html.parser')
        submission_link = next(link for link in doc.select('a') if link.get_text(strip=True) == 'Opening Keynote')
        self.assertEqual(
            submission_link['href'],
            reverse(
                'orga:submissions.content',
                kwargs={'organizer': self.orga1.slug, 'event': self.event1.slug, 'code': self.sub1.code},
            ),
        )
