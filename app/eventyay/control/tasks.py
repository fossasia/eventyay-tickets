import json
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import ProtectedError
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, User
from eventyay.base.models.log import LogEntry
from eventyay.celery_app import app
from eventyay.core.tasks import EventTask


logger = logging.getLogger(__name__)


@app.task(base=EventTask)
def clear_event_data(event):
    event.clear_data()


@app.task(name='eventyay.control.delete_organizer')
@scopes_disabled()
def delete_organizer_data(organizer_id: int, user_id: int | None = None) -> None:
    organizer = Organizer.objects.filter(pk=organizer_id).first()
    if organizer is None:
        logger.warning('Skipping organizer deletion because organizer %s no longer exists', organizer_id)
        return

    user = User.objects.filter(pk=user_id).first() if user_id is not None else None
    organizer_name = str(organizer.name)
    organizer_slug = organizer.slug
    event_ids = list(organizer.events.order_by('pk').values_list('pk', flat=True))

    try:
        for event_id in event_ids:
            try:
                event = Event.objects.select_related('organizer').get(pk=event_id)
            except Event.DoesNotExist:
                continue

            with transaction.atomic():
                event.delete_sub_objects()
                event.delete()

        if not Organizer.objects.filter(pk=organizer_id).exists():
            logger.info('Skipping final organizer cleanup because organizer %s was already deleted', organizer_id)
            return

        with transaction.atomic():
            organizer.delete_sub_objects()
            deleted_count, _ = organizer.delete()

        if deleted_count == 0:
            logger.info('Skipping organizer deletion log because organizer %s was already deleted', organizer_id)
            return

        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(Organizer),
            object_id=organizer_id,
            user=user,
            action_type='eventyay.organizer.deleted',
            data=json.dumps(
                {
                    'organizer_id': organizer_id,
                    'name': organizer_name,
                },
                sort_keys=True,
            ),
        )
    except ProtectedError as exc:
        protected_labels = ', '.join(sorted({obj._meta.label for obj in exc.protected_objects})) or 'unknown'
        organizer = Organizer.objects.filter(pk=organizer_id).first()
        if organizer is not None:
            organizer.log_action(
                'eventyay.organizer.deletion.failed',
                user=user,
                data={
                    'name': organizer_name,
                    'reason': protected_labels,
                },
            )
        logger.warning(
            'Async organizer deletion blocked for organizer %s by protected objects: %s',
            organizer_slug,
            protected_labels,
        )
        raise


@app.task(bind=True, name='eventyay.control.send_admin_email', max_retries=3, default_retry_delay=60, acks_late=True)
@scopes_disabled()
def send_admin_email(self, admin_email_id: int) -> None:
    """
    Celery task to send a platform-wide admin email.

    Follows the same retry/locking pattern as the sendmail plugin's
    send_queued_mail task.
    """
    from celery.exceptions import MaxRetriesExceededError

    from eventyay.base.models.admin_mail import AdminEmailQueue, AdminEmailStatus

    try:
        with transaction.atomic():
            mail = (
                AdminEmailQueue.objects
                .select_for_update(skip_locked=True)
                .filter(pk=admin_email_id)
                .exclude(status__in=[AdminEmailStatus.SENT, AdminEmailStatus.DRAFT, AdminEmailStatus.CANCELLED])
                .first()
            )

            if mail is None:
                logger.info(
                    '[AdminMail] AdminEmailQueue ID %s: not found, already sent, or locked. Skipping.',
                    admin_email_id,
                )
                return

            from django.utils.timezone import now
            current_time = now()
            if mail.scheduled_at and mail.scheduled_at > current_time:
                countdown = max(1, int((mail.scheduled_at - current_time).total_seconds()))
                logger.info(
                    '[AdminMail] AdminEmailQueue ID %s: scheduled for %s, rescheduling in %s seconds.',
                    admin_email_id,
                    mail.scheduled_at,
                    countdown,
                )
                self.retry(countdown=countdown, args=[admin_email_id], throw=False)
                return

            result = mail.send()

            if not result:
                logger.warning('[AdminMail] AdminEmailQueue ID %s: send returned False.', admin_email_id)
            elif mail.status == AdminEmailStatus.SENT:
                logger.info('[AdminMail] AdminEmailQueue ID %s: all emails sent successfully.', admin_email_id)
            else:
                logger.warning('[AdminMail] AdminEmailQueue ID %s: partially sent.', admin_email_id)

    except Exception as exc:
        logger.exception('[AdminMail] Unexpected error for AdminEmailQueue ID %s', admin_email_id)
        try:
            self.retry(exc=exc, args=[admin_email_id])
        except MaxRetriesExceededError:
            logger.error('[AdminMail] Max retries exceeded for AdminEmailQueue ID %s', admin_email_id)
