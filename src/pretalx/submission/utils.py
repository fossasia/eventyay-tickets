import json
from contextlib import suppress

import requests

from pretalx.submission.models import Submission


def fill_recording_urls(event_id, event_slug):
    response = requests.get(f'https://media.ccc.de/public/conferences/{event_id}')
    structure = json.loads(response.content.decode())

    for event in structure.get('events', []):
        if event.get('frontend_link'):
            with suppress(Submission.DoesNotExist):
                talk = Submission.objects.get(event__slug=event_slug, code__iexact=event['slug'])
                talk.recording_url = f'{event["frontend_link"]}/oembed'
                talk.recording_source = 'VOC'
                talk.save()
