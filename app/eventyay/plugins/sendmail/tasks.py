import logging

from celery.exceptions import MaxRetriesExceededError
from django.db import transaction
from django.utils.timezone import now

from eventyay.base.models import Event
from eventyay.base.services.tasks import ProfiledEventTask
from eventyay.celery_app import app


logger = logging.getLogger(__name__)


@app.task(base=ProfiledEventTask, bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def send_queued_mail(self, event_id: int, queued_mail_id: int):
    from eventyay.plugins.sendmail.models import EmailQueue

    if isinstance(event_id, Event):
        original_event_id = event_id.pk
        event = event_id
    else:
        original_event_id = event_id
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            logger.error("[SendMail] Event ID %s not found.", event_id)
            return

    try:
        with transaction.atomic():
            qm = (
                EmailQueue.objects
                .select_for_update(skip_locked=True)
                .filter(pk=queued_mail_id, event=event, sent_at__isnull=True, is_draft=False)
                .first()
            )

            if qm is None:
                logger.info(
                    "[SendMail] EmailQueue ID %s: not found, already sent, or locked by another worker. Skipping.",
                    queued_mail_id,
                )
                return

            current_time = now()
            if qm.scheduled_at and qm.scheduled_at > current_time:
                countdown = max(1, int((qm.scheduled_at - current_time).total_seconds()))
                logger.info(
                    "[SendMail] EmailQueue ID %s: scheduled for %s, rescheduling in %s seconds.",
                    queued_mail_id,
                    qm.scheduled_at,
                    countdown,
                )
                self.retry(countdown=countdown, args=[original_event_id, queued_mail_id], throw=False)
                return

            result = qm.send(async_send=False)

            if not result:
                logger.warning("[SendMail] EmailQueue ID %s: no recipients to send to.", queued_mail_id)
            elif not qm.sent_at:
                logger.warning("[SendMail] EmailQueue ID %s: partially sent, some recipients failed.", queued_mail_id)
            else:
                logger.info("[SendMail] EmailQueue ID %s: all emails sent successfully.", queued_mail_id)

    except Exception as exc:
        logger.exception("[SendMail] Unexpected error for EmailQueue ID %s", queued_mail_id)
        try:
            self.retry(exc=exc, args=[original_event_id, queued_mail_id])
        except MaxRetriesExceededError:
            logger.error("[SendMail] Max retries exceeded for EmailQueue ID %s", queued_mail_id)
