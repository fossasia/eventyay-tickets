from datetime import datetime, timezone
from io import BytesIO
from typing import List

from django.http import FileResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from pretix.base.models import BillingInvoice, OrganizerBillingModel
from pretix.base.models.vouchers import PriceModeChoices


class InvoicePDFGenerator:
    """A class to generate beautifully styled PDF invoices."""

    # Define colors as class constants
    PRIMARY_COLOR = colors.HexColor("#1a73e8")  # Google Blue
    SECONDARY_COLOR = colors.HexColor("#202124")  # Dark Gray
    ACCENT_COLOR = colors.HexColor("#ea4335")  # Google Red

    def __init__(
        self,
        billing_invoice: BillingInvoice,
        organizer_billing_info: OrganizerBillingModel,
    ):
        """Initialize the PDF generator with invoice and billing information.

        Args:
            billing_invoice: BillingInvoice object containing invoice details
            organizer_billing_info: OrganizerBillingModel object containing billing information
        """
        self.billing_invoice = billing_invoice
        self.organizer_billing_info = organizer_billing_info
        self.buffer = BytesIO()
        self.doc = self._create_document()
        self.styles = self._create_styles()

    def _create_document(self) -> SimpleDocTemplate:
        """Create the PDF document with margins."""
        return SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

    def _create_styles(self) -> dict:
        """Create and return all required paragraph styles."""
        styles = getSampleStyleSheet()

        custom_styles = {
            "title": ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=24,
                textColor=self.PRIMARY_COLOR,
                spaceAfter=30,
                alignment=TA_LEFT,
            ),
            "subtitle": ParagraphStyle(
                "CustomSubtitle",
                parent=styles["Heading2"],
                fontSize=14,
                textColor=self.SECONDARY_COLOR,
                alignment=TA_LEFT,
            ),
            "body": ParagraphStyle(
                "CustomBody",
                parent=styles["Normal"],
                fontSize=10,
                leading=14,
                textColor=self.SECONDARY_COLOR,
            ),
            "left_body_white": ParagraphStyle(
                "LeftBodyStyle",
                parent=styles["Normal"],
                fontSize=10,
                leading=14,
                textColor=colors.white,
                alignment=TA_LEFT,
            ),
            "header_white": ParagraphStyle(
                "HeaderStyleWhite",
                parent=styles["Normal"],
                fontSize=10,
                textColor=colors.white,
                fontName="Helvetica-Bold",
            ),
        }

        custom_styles["header_style_center"] = ParagraphStyle(
            "HeaderStyleCenter",
            parent=custom_styles["header_white"],
            alignment=TA_CENTER,
        )

        return custom_styles

    def _create_header(self) -> List[Flowable]:
        """Create the header section of the invoice."""
        header_data = [
            [
                Paragraph("EVENTYAY", self.styles["title"]),
                Paragraph(
                    f"Invoice #{self.billing_invoice.id}", self.styles["subtitle"]
                ),
            ],
            [
                Paragraph("Making Events Happen", self.styles["body"]),
                Paragraph(
                    f"Date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}",
                    self.styles["body"],
                ),
            ],
        ]

        header_table = Table(header_data, colWidths=[self.doc.width / 2] * 2)
        header_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )

        return [
            header_table,
            HRFlowable(width="100%", thickness=1, color=self.PRIMARY_COLOR),
            Spacer(1, 20),
        ]

    def _create_billing_info(self) -> List[Flowable]:
        """Create the billing information section."""
        billing_data = [
            [
                Paragraph(
                    f"<font color='{self.PRIMARY_COLOR.hexval()}'>FROM</font>",
                    self.styles["subtitle"],
                ),
                "",
                Paragraph(
                    f"<font color='{self.PRIMARY_COLOR.hexval()}'>TO</font>",
                    self.styles["subtitle"],
                ),
            ],
            [
                Paragraph("Eventyay Inc.", self.styles["body"]),
                "",
                Paragraph(
                    self.organizer_billing_info.primary_contact_name,
                    self.styles["body"],
                ),
            ],
            [
                Paragraph("123 Tech Street", self.styles["body"]),
                "",
                Paragraph(
                    self.organizer_billing_info.address_line_1, self.styles["body"]
                ),
            ],
            [
                Paragraph("San Francisco, CA 94105", self.styles["body"]),
                "",
                Paragraph(
                    f"{self.organizer_billing_info.city}, {self.organizer_billing_info.country} {self.organizer_billing_info.zip_code}",
                    self.styles["body"],
                ),
            ],
        ]

        billing_table = Table(billing_data, colWidths=[self.doc.width / 3] * 3)
        billing_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )

        return [billing_table, Spacer(1, 30)]

    def _create_event_details(self) -> List[Flowable]:
        """Create the event details section."""
        elements = [Paragraph("EVENT DETAILS", self.styles["subtitle"]), Spacer(1, 10)]

        event_data = [
            ["Event Name:", self.billing_invoice.event.name],
            ["Event ID:", self.billing_invoice.event.slug],
            ["Billing Period:", self.billing_invoice.monthly_bill.strftime("%B %Y")],
        ]

        event_table = Table(
            event_data, colWidths=[self.doc.width / 4, self.doc.width * 3 / 4]
        )
        event_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("TEXTCOLOR", (0, 0), (0, -1), self.PRIMARY_COLOR),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        elements.extend([event_table, Spacer(1, 20)])
        return elements

    def _format_voucher_info(self) -> str:
        """Format the voucher information based on price mode."""
        if self.billing_invoice.voucher_price_mode == PriceModeChoices.SET:
            return f"Set to {self.billing_invoice.currency} {self.billing_invoice.voucher_value:.2f}"
        elif self.billing_invoice.voucher_price_mode == PriceModeChoices.SUBTRACT:
            return f"Subtract {self.billing_invoice.currency} {self.billing_invoice.voucher_value:.2f}"
        elif self.billing_invoice.voucher_price_mode == PriceModeChoices.PERCENT:
            return f"{self.billing_invoice.voucher_value:.0f}% off"
        return ""

    def _create_invoice_details(self) -> List[Flowable]:
        """Create the invoice details section with items and totals."""
        elements = [
            Paragraph("INVOICE DETAILS", self.styles["subtitle"]),
            Spacer(1, 10),
        ]

        items_data = [
            [
                Paragraph("Description", self.styles["header_white"]),
                Paragraph("Price", self.styles["header_style_center"]),
                Paragraph("Discount", self.styles["header_style_center"]),
                Paragraph("Amount", self.styles["header_style_center"]),
            ],
            [
                Paragraph("Ticket Fee", self.styles["body"]),
                f"{self.billing_invoice.currency} {self.billing_invoice.ticket_fee:.2f}",
                f"{self.billing_invoice.currency} {self.billing_invoice.voucher_discount:.2f}",
                f"{self.billing_invoice.currency} {self.billing_invoice.final_ticket_fee:.2f}",
            ],
        ]

        items_table = Table(
            items_data,
            colWidths=[
                self.doc.width * 0.4,
                self.doc.width * 0.2,
                self.doc.width * 0.2,
                self.doc.width * 0.2,
            ],
        )
        items_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27aae1")),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.lightgrey),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )

        elements.extend([items_table, Spacer(1, 10)])

        if (
            self.billing_invoice.voucher_price_mode
            and self.billing_invoice.voucher_price_mode != PriceModeChoices.NONE
        ):
            voucher_text = f"Applied Voucher: {self._format_voucher_info()}"
            elements.extend(
                [Paragraph(voucher_text, self.styles["body"]), Spacer(1, 20)]
            )

        return elements

    def _create_totals(self) -> List[Flowable]:
        """Create the totals section."""
        totals_data = [
            [
                "Original Price:",
                f"{self.billing_invoice.currency} {self.billing_invoice.ticket_fee:.2f}",
            ],
            [
                "Voucher Discount:",
                f"{self.billing_invoice.currency} {self.billing_invoice.voucher_discount:.2f}",
            ],
            ["Tax (0%):", f"{self.billing_invoice.currency} 0.00"],
            [
                "Total:",
                f"{self.billing_invoice.currency} {self.billing_invoice.final_ticket_fee:.2f}",
            ],
        ]

        totals_table = Table(
            totals_data, colWidths=[self.doc.width * 0.8, self.doc.width * 0.2]
        )
        totals_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("TEXTCOLOR", (0, -1), (-1, -1), self.PRIMARY_COLOR),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("LINEABOVE", (0, -1), (-1, -1), 1, self.PRIMARY_COLOR),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        return [totals_table, Spacer(1, 30)]

    def _create_footer(self) -> List[Flowable]:
        """Create the footer section with payment terms and notes."""
        footer_text = f"""
        <para alignment="left" spaceAfter="20">
        <font color="{self.PRIMARY_COLOR.hexval()}" size="12"><b>Payment Terms & Notes</b></font><br/>
        1. Payment is due within 30 days of invoice date<br/>
        2. Your event <b>{str(self.billing_invoice.event.name)}</b> will be moved to non-public if payment is not received within 30 days.
        </para>
        """
        return [Paragraph(footer_text, self.styles["body"])]

    def generate(self) -> FileResponse:
        """
        Generate the complete PDF invoice.
        """
        elements = []
        elements.extend(self._create_header())
        elements.extend(self._create_billing_info())
        elements.extend(self._create_event_details())
        elements.extend(self._create_invoice_details())
        elements.extend(self._create_totals())
        elements.extend(self._create_footer())

        self.doc.build(elements)
        self.buffer.seek(0)
        return FileResponse(
            self.buffer,
            as_attachment=True,
            filename=f"invoice_{self.billing_invoice.event.slug}_{self.billing_invoice.monthly_bill}.pdf",
        )
