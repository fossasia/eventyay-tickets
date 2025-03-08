import secrets

from django.core.management.base import BaseCommand

from pretix.api.models import OAuthApplication


class Command(BaseCommand):
    help = "Create an OAuth2 Application for the Talk SSO Client"

    def handle(self, *args, **options):
        redirect_uris = input(
            "Enter the redirect URI: "
        )  # Get redirect URI from user input

        # Check if the application already exists based on redirect_uri
        if OAuthApplication.objects.filter(redirect_uris=redirect_uris).exists():
            self.stdout.write(
                self.style.WARNING(
                    "OAuth2 Application with this redirect URI already exists."
                )
            )
            return

        # Create the OAuth2 Application
        application = OAuthApplication(
            name="Talk SSO Client",
            client_type=OAuthApplication.CLIENT_CONFIDENTIAL,
            authorization_grant_type=OAuthApplication.GRANT_AUTHORIZATION_CODE,
            redirect_uris=redirect_uris,
            user=None,  # Set a specific user if you want this to be user-specific, else keep it None
            client_id=secrets.token_urlsafe(32),
            client_secret=secrets.token_urlsafe(64),
            hash_client_secret=False,
            skip_authorization=True,
        )
        application.save()

        self.stdout.write(self.style.SUCCESS("Successfully created OAuth2 Application"))
        self.stdout.write(f"Client ID: {application.client_id}")
        self.stdout.write(f"Client Secret: {application.client_secret}")
