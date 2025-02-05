from django.db import models
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nCharField, I18nTextField

from pretix.base.models import LoggedModel


class Page(LoggedModel):
    title = I18nCharField(verbose_name=_('Page title'))
    slug = models.SlugField(
        max_length=150,
        db_index=True,
        verbose_name=_('URL form'),
        help_text=_(
            'This will be used to generate the URL of the page. Please only use latin letters, numbers, dots and dashes. You cannot change this afterwards.'
        ),
    )
    link_on_website_start_page = models.BooleanField(default=False, verbose_name=_('Show link on the website start page'))
    link_in_header = models.BooleanField(default=False, verbose_name=_('Show in header menu on all pages'))
    link_in_footer = models.BooleanField(default=False, verbose_name=_('Show in website footer menu on all pages'))
    confirmation_required = models.BooleanField(
        default=False, verbose_name=_('Require the user to acknowledge this page before the sign up is created (e.g. for terms of service).')
    )
    text = I18nTextField(verbose_name=_('Page content'))
