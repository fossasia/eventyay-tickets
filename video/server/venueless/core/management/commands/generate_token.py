import datetime
import uuid

import jwt
from django.core.management.base import BaseCommand

from venueless.core.models import World
from venueless.core.models.auth import ShortToken


class Command(BaseCommand):
    help = "Generate a valid access token for a world"

    def add_arguments(self, parser):
        parser.add_argument("world_id", type=str)
        parser.add_argument("--trait", type=str, nargs="*", default=[])
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--profile", type=str, default="{}")

    def handle(self, *args, **options):
        world = World.objects.get(id=options["world_id"])
        jwt_config = world.config["JWT_secrets"][0]
        secret = jwt_config["secret"]
        audience = jwt_config["audience"]
        issuer = jwt_config["issuer"]
        iat = datetime.datetime.utcnow()
        exp = iat + datetime.timedelta(days=options["days"])
        payload = {
            "iss": issuer,
            "aud": audience,
            "exp": exp,
            "iat": iat,
            "uid": str(uuid.uuid4()),
            "traits": options["trait"],
        }
        token = jwt.encode(payload, secret, algorithm="HS256").decode("utf-8")
        st = ShortToken.objects.create(world=world, long_token=token, expires=exp)
        self.stdout.write(f"https://{world.domain}/login/{st.short_token}\n")
