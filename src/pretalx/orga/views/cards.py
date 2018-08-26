import tempfile

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.timezone import now
from django.utils.translation import ugettext as _
from django.views.generic import View
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, PageTemplate, Paragraph

from pretalx.common.mixins.views import PermissionRequired
from pretalx.submission.models import SubmissionStates


def ellipsize(text, length=200):
    if len(text) > length:
        return text[:length] + "…"
    return text


class SubmissionCard(Flowable):
    def __init__(self, submission, styles, width):
        super().__init__()
        self.submission = submission
        self.styles = styles
        self.width = width
        self.height = min(2.5 * max(submission.get_duration(), 30) * mm, A4[1])

    def coord(self, x, y, unit=1):
        """
        http://stackoverflow.com/questions/4726011/wrap-text-in-a-table-reportlab
        Helper class to help position flowables in Canvas objects
        """
        x, y = x * unit, self.height - y * unit
        return x, y

    def draw(self):
        self.canv.rect(0, 0, self.width, self.height)

        self.canv.rotate(90)
        self.canv.setFont("Helvetica", 16)
        self.canv.drawString(
            25 * mm, -12 * mm, str(self.submission.submission_type.name)
        )
        self.canv.rotate(-90)

        qr_code = qr.QrCodeWidget(self.submission.orga_urls.quick_schedule.full())
        bounds = qr_code.getBounds()
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        d = Drawing(45, 45, transform=[45 / width, 0, 0, 45 / height, 0, 0])
        d.add(qr_code)
        renderPDF.draw(d, self.canv, 15, 10)

        p = Paragraph(self.submission.title, style=self.styles["Title"])
        w, h = p.wrapOn(self.canv, self.width - 30 * mm, 50 * mm)
        y = h + 10 * mm
        p.drawOn(self.canv, *self.coord(20 * mm, y))

        p = Paragraph(
            ", ".join([s.get_display_name() for s in self.submission.speakers.all()]),
            style=self.styles["Speaker"],
        )
        w, h = p.wrapOn(self.canv, self.width - 30 * mm, 50 * mm)
        y += h + 2 * mm
        p.drawOn(self.canv, *self.coord(20 * mm, y))

        p = Paragraph(
            _('{} minutes, #{}, {}, {}').format(
                self.submission.get_duration(),
                self.submission.code,
                self.submission.content_locale,
                self.submission.state,
            ),
            style=self.styles["Meta"],
        )
        w, h = p.wrapOn(self.canv, self.width - 30 * mm, 50 * mm)
        y += h + 2 * mm
        p.drawOn(self.canv, *self.coord(20 * mm, y))

        if self.submission.abstract:
            p = Paragraph(
                ellipsize(self.submission.abstract, 140), style=self.styles["Meta"]
            )
            w, h = p.wrapOn(self.canv, self.width - 30 * mm, 50 * mm)
            y += h + 2 * mm
            p.drawOn(self.canv, *self.coord(20 * mm, y))

        if self.submission.notes:
            p = Paragraph(
                ellipsize(self.submission.notes, 140), style=self.styles["Meta"]
            )
            w, h = p.wrapOn(self.canv, self.width - 30 * mm, 50 * mm)
            y += h + 2 * mm
            p.drawOn(self.canv, *self.coord(20 * mm, y))


class SubmissionCards(PermissionRequired, View):
    permission_required = 'orga.view_submission_cards'

    def get_permission_object(self):
        return self.request.event

    def get_queryset(self):
        return (
            self.request.event.submissions.select_related('submission_type')
            .prefetch_related('speakers')
            .filter(
                state__in=[
                    SubmissionStates.ACCEPTED,
                    SubmissionStates.CONFIRMED,
                    SubmissionStates.SUBMITTED,
                ]
            )
        )

    def get(self, request, *args, **kwargs):
        if not self.get_queryset().exists():
            messages.warning(request, _('You don\'t have any submissions yet.'))
            return redirect(request.event.orga_urls.submissions)
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            doc = BaseDocTemplate(
                f.name,
                pagesize=A4,
                leftMargin=0,
                rightMargin=0,
                topMargin=0,
                bottomMargin=0,
            )
            doc.addPageTemplates(
                [
                    PageTemplate(
                        id='All',
                        frames=[
                            Frame(
                                0,
                                0,
                                doc.width / 2,
                                doc.height,
                                leftPadding=0,
                                rightPadding=0,
                                topPadding=0,
                                bottomPadding=0,
                                id='left',
                            ),
                            Frame(
                                doc.width / 2,
                                0,
                                doc.width / 2,
                                doc.height,
                                leftPadding=0,
                                rightPadding=0,
                                topPadding=0,
                                bottomPadding=0,
                                id='right',
                            ),
                        ],
                        pagesize=A4,
                    )
                ]
            )
            doc.build(self.get_story(doc))
            f.seek(0)
            r = HttpResponse(content_type='application/pdf')
            timestamp = now().strftime('%Y-%m-%d-%H%M')
            r[
                'Content-Disposition'
            ] = f'attachment; filename="{request.event.slug}_submission_cards_{timestamp}.pdf"'
            r.write(f.read())
            return r

    def get_style(self):
        stylesheet = StyleSheet1()
        stylesheet.add(
            ParagraphStyle(name='Normal', fontName='Helvetica', fontSize=12, leading=14)
        )
        stylesheet.add(
            ParagraphStyle(
                name='Title', fontName='Helvetica-Bold', fontSize=14, leading=16
            )
        )
        stylesheet.add(
            ParagraphStyle(
                name='Speaker', fontName='Helvetica-Oblique', fontSize=12, leading=14
            )
        )
        stylesheet.add(
            ParagraphStyle(name='Meta', fontName='Helvetica', fontSize=10, leading=12)
        )
        return stylesheet

    def get_story(self, doc):
        styles = self.get_style()
        story = []
        for s in self.get_queryset():
            story.append(SubmissionCard(s, styles, doc.width / 2))
        return story
