import logging
import os

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms import SettingsForm
from eventyay.common.urls import get_file_url_path
from eventyay.consts import SizeKey
from eventyay.control.forms import ExtFileField
from eventyay.helpers.image_optimize import optimize_uploaded_image

logger = logging.getLogger(__name__)


class OrganizerSettingsForm(SettingsForm):
    auto_fields = [
        'contact_mail',
        'imprint_url',
        'organizer_info_text',
        'event_list_type',
        'event_list_availability',
        'organizer_homepage_text',
        'organizer_link_back',
        'organizer_header_image_large',
        'community_follow_enabled',
        'community_show_follower_count',
        'giftcard_length',
        'giftcard_expiry_years',
        'locales',
        'region',
        'event_team_provisioning',
        'primary_color',
        'header_background_color',
        'header_text_color',
        'navigation_text_color',
        'menu_text_scroll_over_color',
        'theme_color_success',
        'theme_color_danger',
        'theme_color_background',
        'hover_button_color',
        'video_navigation_background_color',
        'video_sidebar_text_color',
        'video_sidebar_hover_color',
        'theme_round_borders',
        'primary_font',
        'privacy_policy',
    ]

    organizer_logo_image = ExtFileField(
        label=_('Logo'),
        ext_whitelist=('.png', '.jpg', '.gif', '.jpeg', '.svg', '.webp'),
        max_size=settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_IMAGE],
        required=False,
        help_text=_(
            'Upload your organizer logo. The logo is displayed at up to 160 px tall (max-height), width proportional. '
            'We recommend a minimum of 320 px in height for crisp display on retina screens. '
            'The logo will be automatically optimized on save (max 1000 px wide), except for SVG and animated images which remain unmodified.'
        ),
    )

    organizer_header_image = ExtFileField(
        label=_('Header image'),
        ext_whitelist=('.png', '.jpg', '.gif', '.jpeg', '.webp'),
        max_size=settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_IMAGE],
        required=False,
        help_text=_(
            'This image appears at the top of all organizer pages, replacing the default color or pattern. '
            'We recommend an image 1920 px wide and 640 px in height (the center 1920 × 320 px will always be visible). '
            'Images will be automatically optimized to max 1920 px wide on save.'
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs['data-eventyay-file-wrapper'] = 'disabled'
                field.widget.attrs['data-event-settings-image-tools'] = 'enabled'

    def clean(self):
        data = super().clean()
        from eventyay.base.settings import validate_organizer_settings
        validate_organizer_settings(self.obj, data)
        return data

    def save(self):
        for image_field in ('organizer_logo_image', 'organizer_header_image'):
            current_value = self.obj.settings.get(image_field, as_type=str, default='') or ''
            new_value = self.cleaned_data.get(image_field)
            current_file = get_file_url_path(current_value)
            if isinstance(new_value, UploadedFile) and current_file:
                default_storage.delete(current_file)

                base_path, unused_ext = os.path.splitext(current_file)
                orig_ext = self.obj.settings.get(f'{image_field}_original_ext', as_type=str)
                if orig_ext:
                    default_storage.delete(f'{base_path}_original.{orig_ext}')

            if isinstance(new_value, UploadedFile):
                prefix = self.add_prefix(image_field)
                crop_fields = {
                    'x': self.data.get(f'{prefix}_crop_x'),
                    'y': self.data.get(f'{prefix}_crop_y'),
                    'w': self.data.get(f'{prefix}_crop_w'),
                    'h': self.data.get(f'{prefix}_crop_h'),
                }
                crop_box = None
                if all(v not in (None, '') for v in crop_fields.values()):
                    try:
                        crop_x = int(float(crop_fields['x']))
                        crop_y = int(float(crop_fields['y']))
                        crop_w = int(float(crop_fields['w']))
                        crop_h = int(float(crop_fields['h']))
                        if crop_w <= 0 or crop_h <= 0:
                            raise ValueError('Invalid crop dimensions')
                        crop_box = (crop_x, crop_y, crop_x + crop_w, crop_y + crop_h)
                        self.obj.settings.set(
                            f'{image_field}_crop_data',
                            f'{crop_x},{crop_y},{crop_w},{crop_h}',
                        )
                    except (ValueError, TypeError) as e:
                        logger.warning('Invalid crop data for %s (%r): %s', image_field, crop_fields, e)
                        crop_box = None
                self.cleaned_data[image_field] = self._save_optimized(new_value, image_field, crop_box)

        return super().save()

    def _save_optimized(self, uploaded: UploadedFile, setting_key: str, crop_box: tuple[int, int, int, int] | None = None) -> str | UploadedFile:
        """
        Resize and re-encode *uploaded*, persist the original alongside it,
        and return the path to the optimized file.
        """
        try:
            result = optimize_uploaded_image(uploaded, setting_key, crop_box)
        except (ValueError, OSError):
            logger.exception(
                'Image optimization failed for %s; storing original unmodified',
                setting_key,
            )
            uploaded.seek(0)
            return uploaded

        clean_name, unused_ext = os.path.splitext(uploaded.name or setting_key)
        new_filename = self.get_new_filename(clean_name)
        base_path, unused_ext = os.path.splitext(new_filename)

        # Persist the optimized file.
        optimized_name = f'{base_path}.{result.optimized_ext}'
        try:
            optimized_path = default_storage.save(optimized_name, result.optimized)
            logger.info('Stored optimized image at %s', optimized_path)
        except OSError:
            logger.exception('Could not store optimized image for %s', setting_key)
            return uploaded

        # Persist the original file alongside it.
        original_name = f'{base_path}_original.{result.original_ext}'
        try:
            original_path = default_storage.save(original_name, result.original)
            logger.info('Stored original image at %s', original_path)
            self.obj.settings.set(f'{setting_key}_original_ext', result.original_ext)
        except OSError:
            logger.exception('Could not store original image for %s', setting_key)

        # Return a string so Hierarkey stores this path directly
        return f"file://{optimized_path}"
