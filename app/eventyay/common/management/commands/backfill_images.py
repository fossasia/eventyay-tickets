"""Compress stored raster images that exceed a size threshold.

Run on a server after deploying the image compression pipeline to shrink
existing uploads in place and regenerate thumbnails where applicable.

Usage::

    python manage.py backfill_images --backup-dir /path/to/safe/backup
    python manage.py backfill_images --dry-run
    python manage.py backfill_images --min-size-kb 500 --backup-dir /path/to/backup
"""

import logging
import os
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import default_storage
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import Submission, User, Product, Room, Event_SettingsStore, Organizer_SettingsStore
from eventyay.common.image import invalidate_speaker_avatar_caches, is_svg_filename, process_image

logger = logging.getLogger(__name__)

IMAGE_TARGETS = {
    'user': (User, 'avatar', True),
    'submission': (Submission, 'image', False),
    'product': (Product, 'picture', False),
    'room': (Room, 'picture', False),
}

SETTINGS_KEYS = [
    'logo_image',
    'event_logo_image',
    'event_preview_image',
    'og_image',
    'organizer_logo_image',
    'organizer_header_image',
    'invoice_logo_image',
    'startpage_header_image',
]

class MockImageFieldFile:
    def __init__(self, name, store=None):
        self._name = name
        self.storage = default_storage
        self.store = store

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        if self.store:
            self.store.value = f'file://{value}'
            self.store.save(update_fields=['value'])

    def open(self, mode='rb'):
        return self.storage.open(self.name, mode)

    @property
    def size(self):
        return self.storage.size(self.name)

    @property
    def path(self):
        return self.storage.path(self.name)


class Command(BaseCommand):
    help = 'Compress stored raster images larger than a threshold and regenerate thumbnails.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List files that would be compressed without modifying storage.',
        )
        parser.add_argument(
            '--min-size-kb',
            type=int,
            default=getattr(settings, 'IMAGE_BACKFILL_MIN_SIZE_KB', 500),
            help='Only process raster images larger than this many kilobytes.',
        )
        parser.add_argument(
            '--backup-dir',
            type=str,
            help='Directory outside of MEDIA_ROOT to store original files before compression. Required unless --dry-run is set.',
        )
        parser.add_argument(
            '--model',
            action='append',
            choices=list(IMAGE_TARGETS.keys()) + ['settings'],
            help='Only process specific models. Can be specified multiple times.',
        )

    def _backup_file(self, image, backup_dir, prefix):
        if not backup_dir:
            return
        os.makedirs(backup_dir, exist_ok=True)
        basename = os.path.basename(image.name)
        backup_filename = f'{prefix}_{timezone.now():%Y%m%d%H%M%S%f}_{basename}'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        with image.open('rb') as f:
            with open(backup_path, 'wb') as out_f:
                shutil.copyfileobj(f, out_f)
        
        self.stdout.write(f'Backed up to {backup_path}')

    def handle(self, *args, dry_run=False, min_size_kb=500, backup_dir=None, **options):
        if not dry_run and not backup_dir:
            raise CommandError('--backup-dir is required unless --dry-run is set to prevent data loss.')
            
        if backup_dir:
            backup_abs = os.path.abspath(backup_dir)
            media_abs = os.path.abspath(settings.MEDIA_ROOT)
            if backup_abs == media_abs or backup_abs.startswith(media_abs + os.sep):
                raise CommandError(f'--backup-dir ({backup_abs}) must not be inside MEDIA_ROOT ({media_abs}).')
                
        models_to_process = options.get('model') or list(IMAGE_TARGETS.keys()) + ['settings']

        min_bytes = min_size_kb * 1024
        stats = {'compressed': 0, 'failed': 0, 'skipped': 0, 'dry_run': 0}

        def process_image_field(image, model_name, pk, generate_thumbnail):
            if not image or not image.name or is_svg_filename(image.name):
                stats['skipped'] += 1
                return

            try:
                size = image.size
            except (NotImplementedError, AttributeError, OSError):
                stats['failed'] += 1
                logger.exception('Could not read size for %s on %s pk=%s', image.name, model_name, pk)
                self.stderr.write(self.style.ERROR(f'FAILED size read: {model_name} pk={pk} file={image.name}'))
                return

            if size <= min_bytes:
                stats['skipped'] += 1
                return

            try:
                location = image.path
            except (NotImplementedError, AttributeError):
                location = 'remote storage'
                
            if dry_run:
                stats['dry_run'] += 1
                self.stdout.write(f'WOULD compress {model_name} pk={pk} name={image.name} location={location} size={size / 1024:.2f} KB')
                return

            # Perform backup
            try:
                self._backup_file(image, backup_dir, prefix=f'{model_name}_{pk}')
            except OSError as e:
                stats['failed'] += 1
                self.stderr.write(self.style.ERROR(f'FAILED backup: {model_name} pk={pk} file={image.name} error={e}'))
                return False

            # Compress
            if process_image(image=image, generate_thumbnail=generate_thumbnail):
                stats['compressed'] += 1
                try:
                    new_size = image.size
                except (NotImplementedError, AttributeError, OSError):
                    new_size = 'unknown'
                
                size_kb = f'{size / 1024:.2f} KB'
                new_size_kb = f'{new_size / 1024:.2f} KB' if isinstance(new_size, int) else 'unknown'
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Compressed {model_name} pk={pk} name={image.name} location={location} (size: {size_kb} -> {new_size_kb})'
                    )
                )
                return True
            else:
                stats['failed'] += 1
                self.stderr.write(self.style.ERROR(f'FAILED compress: {model_name} pk={pk} file={image.name}'))
                return False

        with scopes_disabled():
            # 1. Process regular models
            for model_key, (model, field_name, generate_thumbnail) in IMAGE_TARGETS.items():
                if model_key not in models_to_process:
                    continue
                queryset = model.objects.exclude(**{f'{field_name}__isnull': True}).exclude(**{field_name: ''})
                for instance in queryset.iterator(chunk_size=200):
                    image = getattr(instance, field_name)
                    success = process_image_field(image, model.__name__, instance.pk, generate_thumbnail)
                    if success and model is User:
                        invalidate_speaker_avatar_caches(instance)
                        
            # 2. Process settings
            if 'settings' in models_to_process:
                for store_model, name in [(Event_SettingsStore, 'EventSettings'), (Organizer_SettingsStore, 'OrganizerSettings')]:
                    for store in store_model.objects.filter(key__in=SETTINGS_KEYS).iterator(chunk_size=200):
                        if not store.value.startswith('file://'):
                            continue
                            
                        file_path = store.value[7:]
                        if not default_storage.exists(file_path):
                            continue
                            
                        image = MockImageFieldFile(file_path, store=store)
                        process_image_field(image, name, store.object_id, generate_thumbnail=False)

        self.stdout.write(
            self.style.SUCCESS(
                'Done. compressed=%(compressed)s failed=%(failed)s skipped=%(skipped)s dry_run=%(dry_run)s' % stats
            )
        )
