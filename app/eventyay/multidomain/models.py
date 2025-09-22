from django.core.cache import cache
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer


class KnownDomain(models.Model):
    domainname = models.CharField(max_length=255, primary_key=True)
    organizer = models.ForeignKey(
        Organizer,
        blank=True,
        null=True,
        related_name='domains',
        on_delete=models.CASCADE,
    )
    event = models.ForeignKey(Event, blank=True, null=True, related_name='domains', on_delete=models.PROTECT)

    class Meta:
        verbose_name = _('Known domain')
        verbose_name_plural = _('Known domains')

    def __str__(self):
        return self.domainname

    @scopes_disabled()
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.event:
            self.event.get_cache().clear()
        elif self.organizer:
            self.organizer.get_cache().clear()
            for event in self.organizer.events.all():
                event.get_cache().clear()
        cache.delete(f'pretix_multidomain_organizer_{self.domainname}')
        cache.delete(f'pretix_multidomain_instance_{self.domainname}')
        cache.delete(f'pretix_multidomain_event_{self.domainname}')

    @scopes_disabled()
    def delete(self, *args, **kwargs):
        if self.event:
            self.event.get_cache().clear()
        elif self.organizer:
            self.organizer.get_cache().clear()
            for event in self.organizer.events.all():
                event.get_cache().clear()
        cache.delete(f'pretix_multidomain_organizer_{self.domainname}')
        cache.delete(f'pretix_multidomain_instance_{self.domainname}')
        cache.delete(f'pretix_multidomain_event_{self.domainname}')
        super().delete(*args, **kwargs)
