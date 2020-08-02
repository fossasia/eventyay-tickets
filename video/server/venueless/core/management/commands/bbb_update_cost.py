import logging
from multiprocessing import cpu_count, pool

import requests
from django.core.management.base import BaseCommand
from lxml import etree

from venueless.core.models import BBBServer
from venueless.core.services.bbb import get_url

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Updated load balancing cost of BBB servers"

    def _update_cost(self, server: BBBServer):
        try:
            meetings_url = get_url("getMeetings", {}, server.url, server.secret)
            r = requests.get(meetings_url)
            r.raise_for_status()
            cost = 0

            root = etree.fromstring(r.text)
            if root.xpath("returncode")[0].text != "SUCCESS":
                raise ValueError("Recordings could not be fetched: " + r.text)

            # Our naive cost calculation probably needs to adjusted at some point. For now, it works like this:
            # Every meeting has a minimal cost of 10, which models that every running meeting requires resources (mostly
            # RAM) on the server. Then, we model an additional cost of 10 * video_senders * video_recipients
            # as well as a cost of 1 * audio_senders * audio_recipients. This follows the bandwidth estimation given
            # at https://docs.bigbluebutton.org/support/faq.html#bandwidth-requirements and we hope that other resources
            # (CPU) are roughly linear to the same values.

            for meet in root.xpath("meetings/meeting"):
                participants = int(meet.xpath("participantCount")[0].text)
                voice_users = int(meet.xpath("voiceParticipantCount")[0].text)
                video_users = int(meet.xpath("videoCount")[0].text)

                cost += (
                    10 + 10 * participants * video_users + participants * voice_users
                )

            server.cost = cost
            server.save(update_fields=["cost"])

        except:
            logger.exception(f"Could not query BBB server {server.id} / {server.url}")

    def handle(self, *args, **options):
        p = pool.ThreadPool(processes=cpu_count())
        p.map(self._update_cost, BBBServer.objects.filter(active=True))
