import datetime as dt
from contextlib import suppress

from dateutil.parser import parse
from django.db import transaction
from django_scopes import scope

from pretalx.person.models import SpeakerProfile, User
from pretalx.schedule.models import Room, TalkSlot
from pretalx.submission.models import (
    Submission,
    SubmissionStates,
    SubmissionType,
    Track,
)


def guess_schedule_version(event):
    if not event.current_schedule:
        return "0.1"

    version = event.current_schedule.version
    prefix = ""
    for separator in [",", ".", "-", "_"]:
        if separator in version:
            prefix, version = version.rsplit(separator, maxsplit=1)
            break
    if version.isdigit():
        version = str(int(version) + 1)
        return prefix + separator + version
    return ""


@transaction.atomic()
def process_frab(root, event):
    """Takes an xml document root and an event, and releases a schedule with
    the data from the xml document.

    Called from the `import_schedule` manage command, at least.
    """
    with scope(event=event):
        for day in root.findall("day"):
            for rm in day.findall("room"):
                room, _ = Room.objects.get_or_create(
                    event=event, name=rm.attrib["name"]
                )
                for talk in rm.findall("event"):
                    _create_talk(talk=talk, room=room, event=event)

        schedule_version = root.find("version").text
        try:
            event.wip_schedule.freeze(schedule_version, notify_speakers=False)
            schedule = event.schedules.get(version=schedule_version)
        except Exception as e:
            raise Exception(
                f'Could not import "{event.name}" schedule version "{schedule_version}": {e}'
            )

        schedule.talks.update(is_visible=True)
        start = schedule.talks.order_by("start").first().start
        end = schedule.talks.order_by("-end").first().end
        if start:
            event.date_from = start.date()
            event.date_to = end.date()
            event.save()
    return (
        f'Successfully imported "{event.name}" schedule version "{schedule_version}".'
    )


def _create_talk(*, talk, room, event):
    date = talk.find("date").text
    start = parse(date + " " + talk.find("start").text)
    hours, minutes = talk.find("duration").text.split(":")
    duration = dt.timedelta(hours=int(hours), minutes=int(minutes))
    duration_in_minutes = duration.total_seconds() / 60
    try:
        end = parse(date + " " + talk.find("end").text)
    except AttributeError:
        end = start + duration
    sub_type = SubmissionType.objects.filter(
        event=event, name=talk.find("type").text, default_duration=duration_in_minutes
    ).first()

    if not sub_type:
        sub_type = SubmissionType.objects.create(
            name=talk.find("type").text or "default",
            event=event,
            default_duration=duration_in_minutes,
        )

    track = Track.objects.filter(event=event, name=talk.find("track").text).first()

    if not track:
        track = Track.objects.create(
            name=talk.find("track").text or "default", event=event
        )

    optout = False
    with suppress(AttributeError):
        optout = talk.find("recording").find("optout").text == "true"

    code = None
    if (
        Submission.objects.filter(code__iexact=talk.attrib["id"], event=event).exists()
        or not Submission.objects.filter(code__iexact=talk.attrib["id"]).exists()
    ):
        code = talk.attrib["id"]
    elif (
        Submission.objects.filter(
            code__iexact=talk.attrib["guid"][:16], event=event
        ).exists()
        or not Submission.objects.filter(code__iexact=talk.attrib["guid"][:16]).exists()
    ):
        code = talk.attrib["guid"][:16]

    sub, _ = Submission.objects.get_or_create(
        event=event, code=code, defaults={"submission_type": sub_type}
    )
    sub.submission_type = sub_type
    sub.track = track
    sub.title = talk.find("title").text
    sub.description = talk.find("description").text
    if talk.find("subtitle").text:
        sub.description = talk.find("subtitle").text + "\n" + (sub.description or "")
    sub.abstract = talk.find("abstract").text
    sub.content_locale = talk.find("language").text or "en"
    sub.do_not_record = optout
    sub.state = SubmissionStates.CONFIRMED
    sub.save()

    for person in talk.find("persons").findall("person"):
        user = User.objects.filter(name=person.text[:60]).first()
        if not user:
            user = User(name=person.text, email=f"{person.text}@localhost")
            user.save()
            SpeakerProfile.objects.create(user=user, event=event)
        sub.speakers.add(user)

    slot, _ = TalkSlot.objects.get_or_create(
        submission=sub, schedule=event.wip_schedule, is_visible=True
    )
    slot.room = room
    slot.is_visible = True
    slot.start = start
    slot.end = end
    slot.save()
