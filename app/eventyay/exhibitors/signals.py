from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from .models import ExhibitorInfo, ContactRequest, Lead, ExhibitorTag


@receiver(post_save, sender=ExhibitorInfo)
def exhibitor_created_handler(sender, instance, created, **kwargs):
    """Handle exhibitor creation"""
    if created:
        # Create default settings or perform setup tasks
        # You can add logic here to:
        # - Send welcome email to exhibitor
        # - Create default links
        # - Set up initial analytics
        pass


@receiver(post_save, sender=ContactRequest)
def contact_request_created_handler(sender, instance, created, **kwargs):
    """Handle new contact requests"""
    if created:
        # Send notification email to exhibitor staff
        exhibitor = instance.exhibitor
        staff_emails = list(
            exhibitor.staff.values_list('user__email', flat=True)
        )
        
        if staff_emails and exhibitor.email:
            staff_emails.append(exhibitor.email)
        
        if staff_emails:
            try:
                subject = f"New Contact Request for {exhibitor.name}"
                message = render_to_string('exhibitors/emails/contact_request.txt', {
                    'exhibitor': exhibitor,
                    'contact_request': instance,
                })
                html_message = render_to_string('exhibitors/emails/contact_request.html', {
                    'exhibitor': exhibitor,
                    'contact_request': instance,
                })
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=staff_emails,
                    html_message=html_message,
                    fail_silently=True
                )
            except Exception:
                # Log error but don't fail the request
                pass


@receiver(post_save, sender=Lead)
def lead_created_handler(sender, instance, created, **kwargs):
    """Handle new lead creation"""
    if created:
        # Update tag usage counts if lead has attendee data
        if instance.attendee and 'interests' in instance.attendee:
            interests = instance.attendee.get('interests', [])
            for interest in interests:
                tag, created = ExhibitorTag.objects.get_or_create(
                    exhibitor=instance.exhibitor,
                    name=interest,
                    defaults={'use_count': 0}
                )
                tag.use_count += 1
                tag.save()


@receiver(pre_save, sender=ExhibitorInfo)
def exhibitor_pre_save_handler(sender, instance, **kwargs):
    """Handle exhibitor updates before saving"""
    # Ensure booth_name is set
    if not instance.booth_name and instance.booth_id:
        instance.booth_name = f'Booth {instance.booth_id}'
    
    # Clean up URLs
    if instance.url and not instance.url.startswith(('http://', 'https://')):
        instance.url = f'https://{instance.url}'


@receiver(post_delete, sender=ExhibitorInfo)
def exhibitor_deleted_handler(sender, instance, **kwargs):
    """Handle exhibitor deletion"""
    # Clean up related files
    if instance.logo:
        try:
            instance.logo.delete(save=False)
        except Exception:
            pass
    
    if instance.banner:
        try:
            instance.banner.delete(save=False)
        except Exception:
            pass


# Email template content for contact requests
CONTACT_REQUEST_EMAIL_TEMPLATE = """
Subject: New Contact Request for {{ exhibitor.name }}

Hello,

You have received a new contact request for {{ exhibitor.name }}:

From: {{ contact_request.attendee_name }} ({{ contact_request.attendee_email }})
Subject: {{ contact_request.subject }}

Message:
{{ contact_request.message }}

{% if contact_request.additional_data %}
Additional Information:
{% for key, value in contact_request.additional_data.items %}
{{ key }}: {{ value }}
{% endfor %}
{% endif %}

Please respond to this inquiry promptly.

Best regards,
The {{ exhibitor.event.name }} Team
"""

CONTACT_REQUEST_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>New Contact Request</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .content { background-color: #fff; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
        .footer { margin-top: 20px; padding: 10px; text-align: center; color: #666; font-size: 12px; }
        .highlight { background-color: #e7f3ff; padding: 10px; border-radius: 3px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>New Contact Request for {{ exhibitor.name }}</h2>
        </div>
        
        <div class="content">
            <div class="highlight">
                <strong>From:</strong> {{ contact_request.attendee_name }} ({{ contact_request.attendee_email }})<br>
                <strong>Subject:</strong> {{ contact_request.subject }}<br>
                <strong>Date:</strong> {{ contact_request.created_at|date:"F j, Y g:i A" }}
            </div>
            
            <h3>Message:</h3>
            <p>{{ contact_request.message|linebreaks }}</p>
            
            {% if contact_request.additional_data %}
            <h3>Additional Information:</h3>
            <ul>
                {% for key, value in contact_request.additional_data.items %}
                <li><strong>{{ key }}:</strong> {{ value }}</li>
                {% endfor %}
            </ul>
            {% endif %}
        </div>
        
        <div class="footer">
            <p>This message was sent through the {{ exhibitor.event.name }} exhibitor contact form.</p>
        </div>
    </div>
</body>
</html>
"""