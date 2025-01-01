from datetime import datetime, timezone
from io import BytesIO

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
    getSampleStyleSheet()

    # Custom Styles with Adjusted Font Sizes
    no_style = ParagraphStyle(
        name="NoStyle",
        fontSize=8,
        alignment=2,
        leftIndent=0,
        rightIndent=0,
        textColor=colors.HexColor("#333333"),
    )
    title_style = ParagraphStyle(
        name="TitleStyle",
        fontSize=20,
        alignment=1,
        leftIndent=0,
        rightIndent=0,
        textColor=colors.HexColor("#333333"),
    )
    body_text_style = ParagraphStyle(
        name="BodyTextStyle",
        fontSize=10,
        alignment=2,
        rightIndent=0,
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
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Header Table: Logo on the left, title and info in a stacked format on the right
    header_data = [
        [
            Table(
                [
                    [
                        Paragraph(
                            f"<b>NO. {billing_invoice.id}</b>",
                            no_style,
                        )
                    ],
                    [
                        Paragraph(
                            f"<b>{str(billing_invoice.event.name)} invoice</b>",
                            title_style,
                        )
                    ],
                    [Paragraph("<br/>", title_style)],
                    [Paragraph("<br/>", title_style)],
                    [Paragraph("<br/>", title_style)],
                    [
                        Paragraph(
                            f"Date: {today}<br/>",
                            body_text_style,
                        )
                    ],
                ],
                colWidths=[6.5 * inch],
            )
        ]
    ]
    header_table = Table(header_data, colWidths=[1.5 * inch, 4.5 * inch])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(header_table)

    # Line Break (Separator)
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(
        HRFlowable(width="120%", thickness=1, color=colors.HexColor("#27aae1"))
    )
    elements.append(Spacer(1, 0.3 * inch))

    # Invoice Information Table
    invoice_data = [
        [
            Paragraph("INVOICE FROM:", header_style),
            "",
            "",
            Paragraph("INVOICE TO:", header_style),
        ],
        [
            Paragraph("Eventyay's name", bold_style),
            "",
            "",
            Paragraph(f"{organizer_billing_info.primary_contact_name}", bold_style),
        ],
        [f"{organizer_billing_info.address_line_1}", "", "", ""],
        [
            "City, Country, ZIP",
            "",
            "",
            f"{organizer_billing_info.city}, {organizer_billing_info.country}, {organizer_billing_info.zip_code}",
        ],
    ]
    invoice_table = Table(
        invoice_data, colWidths=[1.5 * inch, 2 * inch, 1.5 * inch, 1.5 * inch]
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
            Paragraph("PRICE", row_header_style),
            Paragraph("DISCOUNT", row_header_style),
            Paragraph("QUANTITY", row_header_style),
            Paragraph("AMOUNT", row_header_style),
        ],
        [
            "1",
            "Ticket fee for " + f"{billing_invoice.monthly_bill.strftime('%B %Y')}",
            f"{billing_invoice.ticket_fee} {billing_invoice.currency}",
            f"{billing_invoice.voucher_discount} {billing_invoice.currency}",
            "1",
            f"{billing_invoice.final_ticket_fee} {billing_invoice.currency}",
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
        ["SUBTOTAL", f"{billing_invoice.final_ticket_fee}"],
        ["TAX", "0"],
        [
            Paragraph("<b>GRAND TOTAL</b>", bold_style),
            Paragraph(
                f"<b>{billing_invoice.final_ticket_fee} {billing_invoice.currency}</b>",
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

    elements.append(Spacer(1, 0.3 * inch))
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
        buffer, as_attachment=True,
        filename=f"invoice_{billing_invoice.event.slug}_{billing_invoice.monthly_bill}.pdf"
    )
