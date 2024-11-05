from io import BytesIO

from django.conf import settings
from django.http import FileResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


def generate_invoice_pdf(billing_invoice, organizer_billing_info):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Custom Styles with Adjusted Font Sizes
    title_style = ParagraphStyle(
        name="TitleStyle",
        fontSize=16,
        alignment=2,
        textColor=colors.HexColor("#333333"),
    )
    body_text_style = ParagraphStyle(
        name="BodyTextStyle",
        fontSize=10,
        alignment=2,
        textColor=colors.HexColor("#333333"),
    )  # Uniform font size for other text
    header_style = ParagraphStyle(
        name="HeaderStyle",
        fontSize=10,
        alignment=0,
        textColor=colors.HexColor("#27aae1"),
    )
    row_header_style = ParagraphStyle(
        name="HeaderStyle",
        fontSize=10,
        alignment=0,
        textColor=colors.HexColor("#ffffff"),
    )
    bold_style = ParagraphStyle(
        name="BoldStyle",
        fontSize=10,
        leading=12,
        fontName="Helvetica-Bold",
        alignment=0,
    )
    footer_style = ParagraphStyle(
        name="TitleStyle",
        fontSize=10,
        alignment=0,
        textColor=colors.HexColor("#333333"),
    )

    # Header Table: Logo on the left, title and info in a stacked format on the right
    header_data = [
        [
            Table(
                [
                    [
                        Paragraph(
                            f"<b>{str(billing_invoice.event.name)} Invoice</b>",
                            title_style,
                        )
                    ],
                    [Paragraph("<br/>", title_style)],
                    [
                        Paragraph(
                            "Eventyay's address<br/>"
                            f"(818) XXX XXXX<br/>"
                            f"{settings.PRETIX_EMAIL_NONE_VALUE}",
                            body_text_style,
                        )
                    ],
                ],
                colWidths=[4.5 * inch],
            )
        ]
    ]
    header_table = Table(header_data, colWidths=[1.5 * inch, 4.5 * inch])
    header_table.setStyle(
        TableStyle(
            [("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "LEFT")]
        )
    )
    elements.append(header_table)

    # Line Break (Separator)
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#27aae1"))
    )
    elements.append(Spacer(1, 0.2 * inch))

    # Invoice Information Table
    invoice_data = [
        [
            Paragraph("INVOICE TO:", header_style),
            "",
            "",
            Paragraph(f"INVOICE ID: #{billing_invoice.id}", header_style),
        ],
        [
            Paragraph(f"{organizer_billing_info.primary_contact_name}", bold_style),
            "",
            "",
            "Date of Invoice: " + billing_invoice.monthly_bill.strftime("%Y-%m-%d"),
        ],
        [f"{organizer_billing_info.address_line_1}", "", "", ""],
        [
            f"{organizer_billing_info.city}, {organizer_billing_info.country}, {organizer_billing_info.zip_code}",
            "",
            "",
            "",
        ],
    ]
    invoice_table = Table(
        invoice_data, colWidths=[1.5 * inch, 2 * inch, 1 * inch, 2 * inch]
    )
    invoice_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )
    elements.append(invoice_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Itemized Table with Header Background
    item_data = [
        [
            Paragraph("#", row_header_style),
            Paragraph("DESCRIPTION", row_header_style),
            Paragraph("RATE", row_header_style),
            Paragraph("QUANTITY", row_header_style),
            Paragraph("TOTAL", row_header_style),
        ],
        [
            "1",
            "Ticket fee for " + f"{billing_invoice.monthly_bill.strftime('%B %Y')}",
            f"{billing_invoice.ticket_fee} {billing_invoice.currency}",
            "1",
            f"{billing_invoice.ticket_fee} {billing_invoice.currency}",
        ],
    ]
    item_table = Table(
        item_data, colWidths=[0.5 * inch, 3 * inch, 1 * inch, 1 * inch, 1 * inch]
    )
    item_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27aae1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
            ]
        )
    )
    elements.append(item_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Footer Totals Section
    totals_data = [
        ["SUBTOTAL", f"{billing_invoice.ticket_fee}"],
        ["TAX", "0"],
        [
            Paragraph("<b>GRAND TOTAL</b>", bold_style),
            Paragraph(
                f"<b>{billing_invoice.ticket_fee} {billing_invoice.currency}</b>",
                bold_style,
            ),
        ],
    ]
    totals_table = Table(totals_data, colWidths=[5 * inch, 1.5 * inch])
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#27aae1")),
                ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.grey),
                ("LINEBELOW", (0, -1), (-1, -1), 1, colors.HexColor("#27aae1")),
            ]
        )
    )
    elements.append(totals_table)
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Spacer(1, 0.2 * inch))
    notice = f"""
    <font color="#27aae1"><b>NOTICE:</b></font><br/>
    - Payment due within 30 days of the invoice date.<br/>
    - Your event <b>{str(billing_invoice.event.name)}</b> will be moved to non-public if payment is not received
    within 30 days."""

    elements.append(Paragraph(notice, footer_style))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    return FileResponse(
        buffer, as_attachment=True, filename=f"Invoice_{billing_invoice.id}.pdf"
    )
