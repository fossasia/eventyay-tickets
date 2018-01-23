from urllib.parse import urljoin

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.urls import reverse
from django.utils.translation import ugettext as _


class Command(BaseCommand):
    help = 'Initializes your pretalx instance. Only to be used once.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(_('\nWelcome to pretalx! I am the initialization command, and I should be used only once.')))
        self.stdout.write(_('You can abort this command at any time using C-c, and no data will be retained.'))

        self.stdout.write(_('''\nLet\'s get you a user with the right to create new events and access every event on this pretalx instance.'''))

        call_command('createsuperuser')

        url = urljoin(settings.SITE_URL, reverse('orga:dashboard'))
        self.stdout.write(_('\nNow that this is done, you can log in at {url} and get started.').format(url=url))
        self.stdout.write(_('Use the command "import_schedule /path/to/schedule.xml" if you want to import an event."'))
