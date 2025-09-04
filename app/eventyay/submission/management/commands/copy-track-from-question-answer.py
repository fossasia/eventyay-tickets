# Due to misconfiguration, many submissions are missing track. The info is instead in the answer of a question.
# This script copies the track info from the answer to the track field.

import logging

from django.core.management.base import BaseCommand
from django_scopes import scope

from eventyay.base.models import Event
from eventyay.base.models import Submission, TalkQuestion, Track


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Copy track from question answer to track field"

    def add_arguments(self, parser):
        parser.add_argument("event", type=str, help="Event slug")

    def handle(self, *args, **options):
        event = Event.objects.get(slug=options['event'])

        with scope(event=event):
            # Find question with "track" in the label
            track_question = TalkQuestion.all_objects.get(question__icontains="track")
        logger.info('Found question: %s', track_question)
        # Get available tracks
        with scope(event=event):
            tracks = Track.objects.all()
        # Create mapping between track names and track objects.
        track_mapping = {str(track.name): track for track in tracks}
        logger.info('Found tracks: %s', track_mapping)
        updating_submissions = []
        with scope(event=event):
            # Filter submissions with no track and with an answer to a question containing "track"
            queryset = Submission.objects.filter(answers__question=track_question, track=None)
            logger.info('Found %d submissions with no track and with an answer to question %s', queryset.count(), track_question)
            for submission in queryset:
                track_answer = submission.answers.get(question=track_question)
                if track_answer.answer in track_mapping:
                    track = track_mapping[track_answer.answer]
                    submission.track = track
                    logger.info('Submission "%s" (%s) will be updated with track "%s"', submission.title, submission.code, track.name)
                    updating_submissions.append(submission)
        # Update submissions
        if not updating_submissions:
            logger.info('No submission to update')
            return
        with scope(event=event):
            n = Submission.objects.bulk_update(updating_submissions, ['track'])
        logger.info('🎉 Updated %d submissions.', n)
