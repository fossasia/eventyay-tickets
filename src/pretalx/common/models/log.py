from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext_lazy as _

LOG_NAMES = {
    'pretalx.cfp.update': _('The CfP has been modified.'),
    'pretalx.event.create': _('The event has been added.'),
    'pretalx.event.update': _('The event was modified.'),
    'pretalx.event.plugins.enabled': _('The plugin was enabled.'),
    'pretalx.event.plugins.disabled': _('The plugin was disabled.'),
    'pretalx.invite.orga.accept': _('The invitation to the event orga was accepted.'),
    'pretalx.invite.orga.retract': _('An invitation to the event orga was retracted.'),
    'pretalx.invite.orga.send': _('An invitation to the event orga was sent.'),
    'pretalx.invite.reviewer.retract': _('The invitation to the review team was retracted.'),
    'pretalx.invite.reviewer.send': _('The invitation to the review team was sent.'),
    'pretalx.event.invite.orga.accept': _('The invitation to the event orga was accepted.'),  # compat
    'pretalx.event.invite.orga.retract': _('An invitation to the event orga was retracted.'),  # compat
    'pretalx.event.invite.orga.send': _('An invitation to the event orga was sent.'),  # compat
    'pretalx.event.invite.reviewer.retract': _('The invitation to the review team was retracted.'),  # compat
    'pretalx.event.invite.reviewer.send': _('The invitation to the review team was sent.'),  # compat
    'pretalx.mail.create': _('An email was modified.'),
    'pretalx.mail.delete': _('A pending email was deleted.'),
    'pretalx.mail.delete_all': _('All pending emails were deleted.'),
    'pretalx.mail.sent': _('An email was sent.'),
    'pretalx.mail.update': _('An email was modified.'),
    'pretalx.mail_template.create': _('A mail template was added.'),
    'pretalx.mail_template.delete': _('A mail template was deleted.'),
    'pretalx.mail_template.update': _('A mail template was modified.'),
    'pretalx.question.create': _('A question was added.'),
    'pretalx.question.delete': _('A question was deleted.'),
    'pretalx.question.update': _('A question was modified.'),
    'pretalx.question.option.create': _('A question option was added.'),
    'pretalx.question.option.delete': _('A question option was deleted.'),
    'pretalx.question.option.update': _('A question option was modified.'),
    'pretalx.room.create': _('A new room was added.'),
    'pretalx.schedule.release': _('A new schedule version was released.'),
    'pretalx.submission.accept': _('The submission was accepted.'),
    'pretalx.submission.cancel': _('The submission was cancelled.'),
    'pretalx.submission.confirm': _('The submission was confirmed.'),
    'pretalx.submission.confirmation': _('The submission was confirmed.'),  # Legacy
    'pretalx.submission.create': _('The submission was added.'),
    'pretalx.submission.deleted': _('The submission was deleted.'),
    'pretalx.submission.reject': _('The submission was rejected.'),
    'pretalx.submission.resource.create': _('A submission resource was added.'),
    'pretalx.submission.resource.delete': _('A submission resource was deleted.'),
    'pretalx.submission.resource.update': _('A submission resource was modified.'),
    'pretalx.submission.speakers.add': _('A speaker was added to the submission.'),
    'pretalx.submission.speakers.invite': _('A speaker was invited to the submission.'),
    'pretalx.submission.speakers.remove': _('A speaker was removed from the submission.'),
    'pretalx.submission.unconfirm': _('The submission was unconfirmed.'),
    'pretalx.submission.update': _('The submission was modified.'),
    'pretalx.submission.withdraw': _('The submission was withdrawn.'),
    'pretalx.submission.answer.update': _('A submission answer was modified.'),
    'pretalx.submission.answerupdate': _('A submission answer was modified.'),  # compat
    'pretalx.submission.answer.create': _('A submission answer was added.'),
    'pretalx.submission.answercreate': _('A submission answer was added.'),
    'pretalx.submission_type.create': _('A submission type was added.'),
    'pretalx.submission_type.delete': _('A submission type was deleted.'),
    'pretalx.submission_type.make_default': _('The submission type was made default.'),
    'pretalx.submission_type.update': _('A submission type was modified.'),
    'pretalx.speaker.arrived': _('A speaker has been marked as arrived.'),
    'pretalx.speaker.unarrived': _('A speaker has been marked as not arrived.'),
    'pretalx.user.password.reset': _('The password was reset.'),
    'pretalx.user.password.update': _('The password was modified.'),
    'pretalx.user.profile.update': _('The profile was modified.'),
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

    def __str__(self):
        event = getattr(self.event, 'slug', 'None')
        person = getattr(self.person, 'nick', 'None')
        return f'ActivityLog(event={event}, person={person}, content_object={self.content_object}, action_type={self.action_type})'

    def display(self):
        response = LOG_NAMES.get(self.action_type)
        if response is None:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'Unknown log action "{self.action_type}".')
            return self.action_type
        return response
