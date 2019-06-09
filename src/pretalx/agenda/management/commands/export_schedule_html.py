import contextlib
import logging
import re
import shutil
import urllib.parse
from pathlib import Path
from shutil import make_archive

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client, override_settings
from django.utils.timezone import override as override_timezone
from django_scopes import scope, scopes_disabled

from pretalx.common.signals import register_data_exporters
from pretalx.common.utils import rolledback_transaction
from pretalx.event.models import Event


@contextlib.contextmanager
def fake_admin(event):
    with rolledback_transaction():
        event.is_public = True
        event.save()
        client = Client()

        def get(url):
            try:
                # Try getting the file from disk directly first, …
                return get_mediastatic_content(url)
            except FileNotFoundError:
                # … then fall back to asking the views.
                response = client.get(url, is_html_export=True, HTTP_ACCEPT='text/html')
                content = get_content(response)
                return content

        yield get


def find_assets(html):
    """ Find URLs of images, style sheets and scripts included in `html`. """
    soup = BeautifulSoup(html, "lxml")

    for asset in soup.find_all(['script', 'img']):
        yield asset.attrs['src']
    for asset in soup.find_all(['link']):
        if asset.attrs['rel'][0] in ['icon', 'stylesheet']:
            yield asset.attrs['href']


def find_urls(css):
    return re.findall(r'url\("?(/[^")]+)"?\)', css.decode('utf-8'), re.IGNORECASE)


def event_talk_urls(event):
    for talk in event.talks:
        yield talk.urls.public
        yield talk.urls.ical

        for resource in talk.active_resources:
            yield resource.resource.url


def event_speaker_urls(event):
    for speaker in event.speakers:
        profile = speaker.event_profile(event)
        yield profile.urls.public
        yield profile.urls.talks_ical


def event_exporter_urls(event):
    for _, exporter in register_data_exporters.send(event):
        if exporter.public:
            yield exporter(event).urls.base


def schedule_version_urls(event):
    for schedule in event.schedules.filter(version__isnull=False):
        yield schedule.urls.public


def event_urls(event):
    yield event.urls.base
    yield event.urls.schedule
    yield from schedule_version_urls(event)
    yield event.urls.sneakpeek
    yield event.urls.talks
    yield from event_talk_urls(event)
    yield event.urls.speakers
    yield from event_speaker_urls(event)
    yield from event_exporter_urls(event)
    yield event.urls.changelog
    yield event.urls.feed


def get_path(url):
    return urllib.parse.urlparse(url).path


def get_content(response):
    if response.streaming:
        return b''.join(response.streaming_content)
    return response.content


def dump_content(destination, path, getter):
    logging.debug(path)
    content = getter(path)
    if path.endswith('/'):
        path = path + 'index.html'

    path = Path(destination) / path.lstrip('/')
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'wb') as f:
        f.write(content)
    return content


def get_mediastatic_content(url):
    if url.startswith(settings.STATIC_URL):
        local_path = settings.STATIC_ROOT / url[len(settings.STATIC_URL):]
    elif url.startswith(settings.MEDIA_URL):
        local_path = settings.MEDIA_ROOT / url[len(settings.MEDIA_URL):]
    else:
        raise FileNotFoundError()

    with open(local_path, 'rb') as f:
        return f.read()


def export_event(event, destination):
    with override_settings(COMPRESS_ENABLED=True, COMPRESS_OFFLINE=True), override_timezone(event.timezone):
        with fake_admin(event) as get:
            logging.info("Collecting URLs for export")
            urls = [*event_urls(event)]
            assets = set()

            logging.info(f"Exporting {len(urls)} pages")
            for url in map(get_path, urls):
                content = dump_content(destination, url, get)
                assets |= set(map(get_path, find_assets(content)))

            css_assets = set()

            logging.info(f"Exporting {len(assets)} static files from HTML links")
            for url in assets:
                content = dump_content(destination, url, get)

                if url.endswith('.css'):
                    css_assets |= set(find_urls(content))

            logging.info(f"Exporting {len(css_assets)} files from CSS links")
            for url in (get_path(urllib.parse.unquote(url)) for url in css_assets):
                dump_content(destination, url, get)


def delete_directory(path):
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(path)


def get_export_path(event):
    return settings.HTMLEXPORT_ROOT / event.slug


def get_export_zip_path(event):
    return get_export_path(event).with_suffix('.zip')


class Command(BaseCommand):

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('event', type=str)
        parser.add_argument('--zip', action='store_true')

    def handle(self, *args, **options):
        event_slug = options.get('event')

        with scopes_disabled():
            try:
                event = Event.objects.get(slug__iexact=event_slug)
            except Event.DoesNotExist:
                raise CommandError(f'Could not find event with slug "{event_slug}".')

        with scope(event=event):
            logging.info(f'Exporting {event.name}')
            export_dir = get_export_path(event)
            zip_path = get_export_zip_path(event)
            tmp_dir = export_dir.with_name(export_dir.name + '-new')

            delete_directory(tmp_dir)
            tmp_dir.mkdir()

            try:
                export_event(event, tmp_dir)
                delete_directory(export_dir)
                tmp_dir.rename(export_dir)
            finally:
                delete_directory(tmp_dir)

            logging.info(f'Exported to {export_dir}')

            if options.get('zip'):
                make_archive(
                    root_dir=settings.HTMLEXPORT_ROOT,
                    base_dir=event.slug,
                    base_name=zip_path.parent / zip_path.stem,
                    format='zip',
                )

                logging.info(f'Exported to {zip_path}')
