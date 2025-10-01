from typing import Tuple

from django.utils.translation import gettext_lazy as _

from eventyay.base.models import OrderPosition
from eventyay.base.ticketoutput import BaseTicketOutput


class BadgeOutputProvider(BaseTicketOutput):
    identifier = 'badge'
    verbose_name = _('Badge')
    download_button_text = _('Download Badge')
    multi_download_enabled = True

    def generate(self, op: OrderPosition) -> Tuple[str, str, bytes]:
        try:
            from .exporters import OPTIONS, render_pdf

            pdf_buffer = render_pdf(op.order.event, [op], OPTIONS['one'])
            if pdf_buffer is None:
                raise Exception('Failed to generate PDF')

            if hasattr(pdf_buffer, 'getvalue'):
                pdf_content = pdf_buffer.getvalue()
            else:
                pdf_content = pdf_buffer

            return 'badge.pdf', 'application/pdf', pdf_content

        except Exception as e:
            raise e

    @property
    def settings_form_fields(self):
        return {}  # No settings needed for now
