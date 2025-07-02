from django.db import models
from django.utils.timezone import now
from pretix.base.models import Event, Order, OrderPosition, Team, User
from pretix.base.services.mail import mail


class QueuedMail(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="queued_mails")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)  # sender
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.CASCADE)
    position = models.ForeignKey(OrderPosition, null=True, blank=True, on_delete=models.SET_NULL)
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.CASCADE)
    recipient = models.EmailField()
    raw_subject = models.TextField(null=True, blank=True)  # This stores the raw subject (i.e. with placeholders)
    raw_message = models.TextField(null=True, blank=True)  # This stores the message template (i.e. with placeholders)
    subject = models.TextField()
    message = models.TextField()
    reply_to = models.CharField(max_length=1000, null=True, blank=True)
    bcc = models.TextField(null=True, blank=True)  # comma-separated string
    locale = models.CharField(max_length=16, null=True, blank=True)
    attachments = models.JSONField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"QueuedMail(to={self.recipient}, subject={self.subject[:30]}, sent={self.sent})"

    def make_text(self, signature=None):
        text = self.message
        if signature:
            if not signature.strip().startswith("-- "):
                signature = f"-- \n{signature.strip()}"
            text = f"{text.strip()}\n\n{signature}"
        return text

    def send(self, event_signature=None):
        if self.sent:
            return  # Already sent
        
        body = self.make_text(event_signature)
        try:
            mail(
                email=self.recipient,
                subject=self.subject,
                template=body,
                context={},
                event=self.event,
                locale=self.locale,
                order=self.order,
                position=self.position,
                attach_cached_files=self.attachments,
                user=self.user
            )
        except Exception:
            return False
            # pass
        
        self.sent = True
        self.sent_at = now()
        self.save()

        return True
