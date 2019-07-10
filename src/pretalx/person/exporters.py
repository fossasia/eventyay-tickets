import csv
import io

from django.utils.translation import gettext_lazy as _

from pretalx.common.exporter import BaseExporter
from pretalx.submission.models import SubmissionStates


class CSVSpeakerExporter(BaseExporter):

    public = False
    icon = 'fa-users'
    identifier = 'speakers.csv'
    verbose_name = _('Speaker CSV')

    def render(self, **kwargs):
        content = io.StringIO()
        writer = csv.DictWriter(content, fieldnames=['name', 'email', 'confirmed'])
        writer.writeheader()
        for speaker in self.event.submitters:
            accepted_talks = speaker.submissions.filter(
                event=self.event, state=SubmissionStates.ACCEPTED
            ).exists()
            confirmed_talks = speaker.submissions.filter(
                event=self.event, state=SubmissionStates.CONFIRMED
            ).exists()
            if not accepted_talks and not confirmed_talks:
                continue
            writer.writerow(
                {
                    'name': speaker.get_display_name(),
                    'email': speaker.email,
                    'confirmed': str(bool(confirmed_talks)),
                }
            )

        return (f'{self.event.slug}-speakers.csv', 'text/plain', content.getvalue())
