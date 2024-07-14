from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.sites.models import Site

class Command(BaseCommand):
    help = 'Create SocialApp entries for Eventyay-ticket Provider'

    def add_arguments(self, parser):
        parser.add_argument('--eventyay-ticket-client-id', type=str, help='Eventyay-Ticket Provider Client ID')
        parser.add_argument('--eventyay-ticket-secret', type=str, help='Eventyay-Ticket Provider Secret')

    def handle(self, *args, **options):
        site = Site.objects.get(pk=settings.SITE_ID)
        eventyay_ticket_client_id = options.get('eventyay-ticket-client-id') or input('Enter Eventyay-Ticket Provider Client ID: ')
        eventyay_ticket_secret = options.get('eventyay-ticket-secret') or input('Enter Eventyay-Ticket Provider Secret: ')

        if not SocialApp.objects.filter(provider='eventyay').exists():
            custom_app = SocialApp.objects.create(
                provider='eventyay',
                name='Eventyay Ticket Provider',
                client_id=eventyay_ticket_client_id,
                secret=eventyay_ticket_secret,
                key=''
            )
            custom_app.sites.add(site)
            self.stdout.write(self.style.SUCCESS('Successfully created Eventyay-ticket Provider SocialApp'))
