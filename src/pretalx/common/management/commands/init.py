from argparse import RawTextHelpFormatter
from os import environ
from urllib.parse import urljoin

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.urls import reverse

from pretalx.event.utils import create_organiser_with_team
from pretalx.person.models import User

env_prefix = "PRETALX_INIT_ORGANISER_"
organiser_name_env = f"{env_prefix}NAME"
organiser_name_default = "The Conference Organiser"
organiser_slug_env = f"{env_prefix}SLUG"
organiser_slug_default = "conforg"


def prompt_nonempty(prompt):  # pragma: no cover
    result = input(prompt).strip()
    while not result:
        result = input("This value is required, please enter some value to proceed: ")
    return result


class Command(BaseCommand):  # pragma: no cover
    help = "Initializes your pretalx instance. Only to be used once."

    def add_arguments(self, parser):
        parser.formatter_class = RawTextHelpFormatter
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Suppresses all interactive prompts and uses environment variables instead. "
            "If environment variables are missing, the command will fail. "
            "Required environment variables:\n"
            'DJANGO_SUPERUSER_EMAIL="new-superuser-email@example.org"\n'
            'DJANGO_SUPERUSER_PASSWORD="[SECRET]"\n'
            f'{organiser_name_env}="{organiser_name_default}"\n'
            f'{organiser_slug_env}="{organiser_slug_default}"',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                "\nWelcome to pretalx! This is my initialization command, please use it only once."
            )
        )
        self.stdout.write(
            "You can abort this command at any time using C-c, and it will save no data."
        )

        self.stdout.write(
            """\nLet\'s get you a user with the right to create new events and access every event on this pretalx instance."""
        )

        call_command("createsuperuser", interactive=options["interactive"])

        user = User.objects.order_by("-id").filter(is_administrator=True).first()

        self.stdout.write(
            """\nLet\'s also create a first organiser: This will allow you to invite further people and create events."""
        )
        self.stdout.write("\n")

        organiser_name = self.get_nonempty(
            f'Name (e.g. "{organiser_name_default}"): ',
            organiser_name_env if not options["interactive"] else None,
        )
        organiser_slug = self.get_nonempty(
            f'Slug (e.g. "{organiser_slug_default}", used in urls): ',
            organiser_slug_env if not options["interactive"] else None,
        )

        organiser, team = create_organiser_with_team(
            name=organiser_name, slug=organiser_slug, users=[user]
        )

        event_url = urljoin(settings.SITE_URL, reverse("orga:event.create"))
        team_url = urljoin(
            settings.SITE_URL,
            reverse(
                "orga:organiser.teams.view",
                kwargs={"organiser": organiser.slug, "pk": team.pk},
            ),
        )
        self.stdout.write(self.style.SUCCESS("\nNow that this is done, you can:"))
        self.stdout.write(f" - Create your first event at {event_url}")
        self.stdout.write(f" - Invite somebody to the organiser team at {team_url}")

    def get_nonempty(self, prompt, env_varname=None):
        if not env_varname:
            return prompt_nonempty(prompt)

        if env_varname not in environ:
            raise ValueError(
                f"Environment variable {env_varname} is required but undefined."
            )

        self.stdout.write(f"{prompt}[{'used environment variable:'} {env_varname}]")
        return environ[env_varname]
