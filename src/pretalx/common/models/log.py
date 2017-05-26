from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext_lazy as _

LOG_NAMES = {
    'pretalx.cfp.update': _('The CfP has been modified.'),
    'pretalx.event.create': _('The event has been created.'),
    'pretalx.event.invite.orga.send': _('An invitation to the event orga was sent.'),
    'pretalx.event.invite.orga.retract': _('An invitation to the event orga was retracted.'),
    'pretalx.event.invite.orga.accept': _('The invitation to the event orga was accepted.'),
    'pretalx.event.update': _('The event was updated.'),
    'pretalx.mail.sent': _('An email was sent.'),
    'pretalx.mail.delete': _('A pending email was deleted.'),
    'pretalx.mail.delete_all': _('All pending emails were deleted.'),
    'pretalx.mail_template.delete': _('A mail template was deleted.'),
    'pretalx.question.delete': _('A question was deleted.'),
    'pretalx.submission.accept': _('The submission was accepted.'),
    'pretalx.submission.confirmation': _('The submission was confirmed.'),
    'pretalx.submission.create': _('The submission was created.'),
    'pretalx.submission.reject': _('The submission was rejected.'),
    'pretalx.submission.speakers.add': _('A speaker was added to the submission.'),
    'pretalx.submission.speakers.remove': _('A speaker was removed from the submission.'),
    'pretalx.submission.update': _('The submission was updated.'),
    'pretalx.submission.withdrawal': _('The submission was withdrawn.'),
    'pretalx.submission_type.delete': _('A submission type was deleted.'),
    'pretalx.submission_type.make_default': _('The submission type was made default.'),
    'pretalx.user.password.update': _('The password was updated.'),
    'pretalx.user.profile.update': _('The profile was updated.'),
    'pretalx.user.password_reset': _('The password was reset.'),
}


class ActivityLog(models.Model):
    event = models.ForeignKey(
        to='event.Event',
        on_delete=models.PROTECT,
        related_name='log_entries',
        null=True, blank=True,
    )
    person = models.ForeignKey(
        to='person.User',
        on_delete=models.PROTECT,
        related_name='log_entries',
        null=True, blank=True,
    )
    content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
    )
    object_id = models.PositiveIntegerField(
        db_index=True
    )
    content_object = GenericForeignKey(
        'content_type', 'object_id',
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, db_index=True,
    )
    action_type = models.CharField(
        max_length=200,
    )
    data = models.TextField(
        null=True, blank=True
    )
    is_orga_action = models.BooleanField(default=False)

    class Meta:
        ordering = ('-timestamp', )

    def display(self):
        response = LOG_NAMES.get(self.action_type)
        if response is None:
            return self.action_type
        return response
