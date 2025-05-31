import sys

from django.core.management.base import BaseCommand
from django_scopes import scopes_disabled

from pretix.base.i18n import get_language_without_region
from pretix.base.models import Customer, Event, Order, Organizer


class Command(BaseCommand):
    help = 'Create customer account for all orders with email address.'

    def add_arguments(self, parser):
        parser.add_argument('--organizer-slug', type=str, help='Organizer Slug')
        parser.add_argument('--event-slug', type=str, help='Event Slug')

    def handle(self, *args, **options):
        organizer_slug = options.get('organizer-slug') or input('Enter Organizer Slug: ')
        event_slug = options.get('event-slug') or input('Enter Event Slug: ')

        try:
            with scopes_disabled():
                organizer = Organizer.objects.get(slug=organizer_slug)
                event = Event.objects.get(slug=event_slug, organizer=organizer)
        except Organizer.DoesNotExist:
            self.stderr.write(self.style.ERROR('Organizer not found.'))
            sys.exit(1)
        except Event.DoesNotExist:
            self.stderr.write(self.style.ERROR('Event not found.'))
            sys.exit(1)

        if not organizer.settings.customer_accounts or not organizer.settings.customer_accounts_native:
            self.stderr.write(self.style.ERROR('Organizer not enable customer account yet.'))
            sys.exit(1)

        with scopes_disabled():
            orders = Order.objects.filter(event=event)
            # Get all orders email and check if they have a customer account or not
            for order in orders:
                if order.email:
                    customer = Customer.objects.filter(email__iexact=order.email).first()
                    if not customer:
                        name_parts_data = {
                            '_scheme': 'full',
                            'full_name': order.email.split('@')[0],
                        }
                        customer = organizer.customers.create(
                            email=order.email,
                            name_parts=name_parts_data,
                            is_active=True,
                            is_verified=False,
                            locale=get_language_without_region(),
                        )
                        customer.set_unusable_password()
                        customer.save()
                    # Update order with customer
                    if order.customer is None:
                        order.customer = customer
                        order.save()
