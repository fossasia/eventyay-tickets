from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def exhibitor_count(event):
    """Get the total number of exhibitors for an event."""
    from ..models import ExhibitorInfo
    return ExhibitorInfo.objects.filter(event=event, is_active=True).count()


@register.simple_tag
def exhibitor_lead_count(exhibitor):
    """Get the total number of leads for an exhibitor."""
    return exhibitor.leads.count()


@register.simple_tag
def exhibitor_booth_qr(exhibitor):
    """Generate QR code for exhibitor booth."""
    try:
        import qrcode
        from io import BytesIO
        import base64
        
        # Create QR code with exhibitor key
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(exhibitor.key)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return mark_safe(f'<img src="data:image/png;base64,{img_str}" alt="QR Code for {exhibitor.name}" class="exhibitor-qr-code">')
    except ImportError:
        return mark_safe('<div class="alert alert-warning">QR code generation requires the qrcode package</div>')


@register.filter
def exhibitor_logo_url(exhibitor):
    """Get the URL for an exhibitor's logo."""
    if exhibitor.logo:
        return exhibitor.logo.url
    return None


@register.inclusion_tag('exhibitor/tags/exhibitor_card.html')
def exhibitor_card(exhibitor, show_leads=False):
    """Render an exhibitor card."""
    return {
        'exhibitor': exhibitor,
        'show_leads': show_leads,
        'lead_count': exhibitor.leads.count() if show_leads else 0
    }