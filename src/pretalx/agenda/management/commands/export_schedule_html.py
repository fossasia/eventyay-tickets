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

from pretalx.common.utils import rolledback_transaction
from pretalx.event.models import Event, Team
from pretalx.person.models import User


@contextlib.contextmanager
def fake_admin(event):
    with rolledback_transaction():
        user = User.objects.create_user(
            email=f'export-{event.slug}@pretalx.invalid',
            name=f'export-{event.slug}',
            locale=event.locale,
        )
        team = Team.objects.create(
            organiser=event.organiser,
            name=f'export-team-{event.slug}',
            can_change_submissions=True,
        )
        team.limit_events.add(event)
        team.members.add(user)

        c = Client()
        c.force_login(user)

        def get(url):
            try:
                # try getting the file from disk directly first, ...
                return get_mediastatic_content(url)
            except FileNotFoundError:
                # ... then fall-back to asking the views.
                response = c.get(url, is_html_export=True, HTTP_ACCEPT='text/html')
                content = get_content(response)
                return content

        yield get


def find_assets(html):
    """ find URLs of additional files needed to render `html`, e.g. images, js, css, ... """
    soup = BeautifulSoup(html, "lxml")

    for asset in soup.find_all(['script', 'img', 'link']):
        if asset.name in ['script', 'img']:
            yield asset.attrs['src']
        elif asset.name == 'link':
            if asset.attrs['rel'][0] in ['icon', 'stylesheet']:
                yield asset.attrs['href']


def find_urls(css):
    return re.findall(r'url\("?(/[^")]+)"?\)', css.decode('utf-8'), re.IGNORECASE)


def urls_event_talks(event):
    for talk in event.talks:
        yield talk.urls.public
        yield talk.urls.ical

        for resource in talk.active_resources:
            yield resource.resource.url


def urls_event_speakers(event):
    for speaker in event.speakers:
        profile = speaker.event_profile(event)
        yield profile.urls.public
        yield profile.urls.talks_ical


def urls_schedule_versions(event):
    for schedule in event.schedules.filter(version__isnull=False):
        yield schedule.urls.public


def urls_event(event):
    yield event.urls.base
    yield event.urls.schedule
    yield from urls_schedule_versions(event)
    yield event.urls.sneakpeek
    yield event.urls.talks
    yield from urls_event_talks(event)
    yield event.urls.speakers
    yield from urls_event_speakers(event)
    yield event.urls.changelog
    yield event.urls.feed
    yield event.urls.frab_xml
    yield event.urls.frab_json
    yield event.urls.frab_xcal
    yield event.urls.ical


def get_path(url):
    return urllib.parse.urlparse(url).path


def get_content(response):
    if response.streaming:
        return b''.join(response.streaming_content)
    else:
        return response.content


def dump_content(dest, path, content):
    if path.endswith('/'):
        path = path + 'index.html'

    path = Path(dest) / path.lstrip('/')
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'wb') as f:
        f.write(content)


def get_mediastatic_content(url):
    if url.startswith(settings.STATIC_URL):
        local_path = settings.STATIC_ROOT / url[len(settings.STATIC_URL):]
    elif url.startswith(settings.MEDIA_URL):
        local_path = settings.MEDIA_ROOT / url[len(settings.MEDIA_URL):]
    else:
        raise FileNotFoundError()

    with open(local_path, 'rb') as f:
        return f.read()


def export_event(event, dest):
    with override_settings(COMPRESS_ENABLED=True, COMPRESS_OFFLINE=True), override_timezone(event.timezone):
        with fake_admin(event) as get:
            logging.info("collecting page URLs")
            urls = [*urls_event(event)]
            assets = set()

            logging.info(f"exporting {len(urls)} pages")
            for url in map(get_path, urls):
                logging.debug(url)
                content = get(url)
                dump_content(dest, url, content)
                assets |= set(map(get_path, find_assets(content)))

            css_assets = set()

            logging.info(f"exporting {len(assets)} assets linked to in HTML")
            for url in assets:
                logging.debug(url)
                content = get(url)

                dump_content(dest, url, content)

                if url.endswith('.css'):
                    css_assets |= set(find_urls(content))

            logging.info(f"exporting {len(css_assets)} assets linked to in CSS")
            for url in (get_path(urllib.parse.unquote(url)) for url in css_assets):
                logging.debug(url)
                content = get(url)
                dump_content(dest, url, content)


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

        try:
            event = Event.objects.get(slug__iexact=event_slug)
        except Event.DoesNotExist:
            raise CommandError(f'Could not find event with slug "{event_slug}".')

        logging.info(f'exporting {event.name}')

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

        logging.info(f'exported to {export_dir}')

        if options.get('zip'):
            make_archive(
                root_dir=settings.HTMLEXPORT_ROOT,
                base_dir=event.slug,
                base_name=zip_path.parent / zip_path.stem,
                format='zip',
            )

            logging.info(f'exported to {zip_path}')
