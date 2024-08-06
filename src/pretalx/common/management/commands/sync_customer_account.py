import requests

from allauth.socialaccount.models import SocialAccount
from django.core.management.base import BaseCommand

from pretalx.event.models import Organiser
from pretalx.person.models import User


class Command(BaseCommand):
    help = 'Sync customer account from Eventyay-ticket'

    def add_arguments(self, parser):
        parser.add_argument('--ticket-organizer-slug', type=str, help='Ticket Organizer Slug')
        parser.add_argument('--ticket-url', type=str, help='Ticket Url')
        parser.add_argument('--ticket-token', type=str, help='Ticket token')

    def handle(self, *args, **options):
        organizer_slug = options.get('ticket-organizer-slug') or input('Enter Ticket Organizer Slug you want to retrieve customer: ')
        ticket_url = options.get('ticket-url') or input('Enter Ticket Url which be using for retrieve customer data from Ticket: ')
        ticket_token = options.get('ticket-token') or input('Enter Ticket token which be using for retrieve customer data from Ticket: ')
        try:
            Organiser.objects.get(slug=organizer_slug)
        except Organiser.DoesNotExist:
            self.stderr.write(self.style.ERROR('Organizer not found.'))
            return
        url = f'{ticket_url}/api/v1/organizers/{organizer_slug}/customers/'

        headers = {"Authorization": 'Token ' + ticket_token}
        try:
            response = requests.get(url, headers=headers)
            customer_dict = response.json()['results']
        except Exception as e:
            self.stderr.write(self.style.ERROR('Error when getting customer data from Ticket, please check input data.'))
            return

        for customer in customer_dict:
            try:
                user = User.objects.filter(email=customer['email']).first()
                if not user:
                    user = User.objects.create_user(
                        email=customer['email'],
                        name=customer['name'],
                        password=None,
                        code=customer['identifier'],
                    )
                    user.save()
                    social_account = SocialAccount.objects.create(
                        user=user,
                        provider=organizer_slug,
                        uid=customer['identifier'],
                    )
                    social_account.save()
                    self.stdout.write(self.style.SUCCESS('Customer created: ' + user.email))
            except Exception as e:
                self.stderr.write(self.style.ERROR('Error when creating customer: ' + customer['email']))
                continue
        self.stdout.write(self.style.SUCCESS(
            'Successfully created Eventyay-ticket Provider SocialApp'))
