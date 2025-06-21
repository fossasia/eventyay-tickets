import datetime as dt

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from pretalx.event.models import Event


@pytest.fixture
def event():
    with scopes_disabled():
        return Event.objects.create(
            name="Event",
            slug="event",
            is_public=True,
            email="orga@orga.org",
            locale_array="en,de",
            locale="en",
            date_from=dt.date.today(),
            date_to=dt.date.today(),
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "locale_array,count",
    (
        ("de", 1),
        ("de,en", 2),
    ),
)
def test_locales(event, locale_array, count):
    event.locale_array = locale_array
    event.save()
    assert len(event.locales) == count
    assert len(event.named_locales) == count


@pytest.mark.django_db
def test_initial_data(event):
    with scope(event=event):
        assert event.cfp
        assert event.cfp.default_type
        assert event.get_mail_template("submission.state.accepted")
        assert event.get_mail_template("submission.new")
        assert event.get_mail_template("submission.state.rejected")
        assert event.schedules.count()
        assert event.wip_schedule

        event.cfp.delete()
        event.mail_templates.all().delete()
        event.build_initial_data()

        assert event.cfp
        assert event.cfp.default_type
        assert event.get_mail_template("submission.state.accepted")
        assert event.get_mail_template("submission.new")
        assert event.get_mail_template("submission.state.rejected")
        assert event.schedules.count()
        assert event.wip_schedule


@pytest.mark.parametrize(
    "slug",
    (
        "_global",
        "__debug__",
        "api",
        "csp_report",
        "events",
        "download",
        "healthcheck",
        "jsi18n",
        "locale",
        "metrics",
        "orga",
        "redirect",
        "widget",
    ),
)
@pytest.mark.django_db
def test_event_model_slug_permitted_validation(slug):
    with pytest.raises(ValidationError):
        Event(
            name="Event",
            slug=slug,
            is_public=True,
            email="orga@orga.org",
            locale_array="en,de",
            locale="en",
            date_from=dt.date.today(),
            date_to=dt.date.today(),
        ).clean_fields()


@pytest.mark.django_db
def test_event_model_slug_uniqueness():
    with scopes_disabled():
        Event.objects.create(
            name="Event",
            slug="slog",
            is_public=True,
            email="orga@orga.org",
            locale_array="en,de",
            locale="en",
            date_from=dt.date.today(),
            date_to=dt.date.today(),
        )
        assert Event.objects.count() == 1
        with pytest.raises(IntegrityError):
            Event.objects.create(
                name="Event",
                slug="slog",
                is_public=True,
                email="orga@orga.org",
                locale_array="en,de",
                locale="en",
                date_from=dt.date.today(),
                date_to=dt.date.today(),
            ).clean_fields()


@pytest.mark.django_db
def test_event_copy_settings(event, submission_type, choice_question, track):
    with scope(event=event):
        event.custom_domain = "https://testeventcopysettings.example.org"
        event.settings.random_value = "testcopysettings"
        accept_template = event.get_mail_template("submission.state.accepted")
        accept_template.text = "testtemplate"
        accept_template.save()
        event.feature_flags = {"testing": "working"}
        choice_question.tracks.add(track)
        event.cfp.deadline = now()
        event.cfp.save()
        assert event.submission_types.count() == 2
    with scopes_disabled():
        new_event = Event.objects.create(
            organiser=event.organiser,
            locale_array="de,en",
            name="Teh Name",
            slug="tn",
            timezone="Europe/Berlin",
            email="tehname@example.org",
            locale="de",
            date_from=dt.date.today(),
            date_to=dt.date.today(),
        )
    with scopes_disabled():
        assert new_event.submission_types.count() == 1
        new_event.copy_data_from(event)
    with scope(event=new_event):
        assert new_event.submission_types.count() == 2
        accept_template = new_event.get_mail_template("submission.state.accepted")
        assert accept_template.text == "testtemplate"
        assert new_event.settings.random_value == "testcopysettings"
        assert not new_event.custom_domain
        assert new_event.feature_flags == {"testing": "working"}
        assert new_event.get_feature_flag("use_tracks") is True
        assert new_event.cfp.deadline == event.cfp.deadline
        assert new_event.questions.count()
        assert new_event.questions.first().options.count()


@pytest.mark.django_db
def test_event_copy_settings_with_exceptions(event):
    with scope(event=event):
        event.feature_flags = {"testing": "working"}
        event.cfp.deadline = now()
        event.cfp.save()
    with scopes_disabled():
        new_event = Event.objects.create(
            organiser=event.organiser,
            locale_array="de,en",
            name="Teh Name",
            slug="tn",
            timezone="Europe/Berlin",
            email="tehname@example.org",
            locale="de",
            date_from=dt.date.today(),
            date_to=dt.date.today(),
        )
        new_event.copy_data_from(event, skip_attributes=["feature_flags", "deadline"])
    with scope(event=new_event):
        assert new_event.feature_flags != {"testing": "working"}
        assert not new_event.cfp.deadline


@pytest.mark.django_db
def test_event_get_default_type(event):
    with scope(event=event):
        assert event.submission_types.count() == 1
        event._get_default_submission_type()
        assert event.submission_types.count() == 1


@pytest.mark.django_db
def test_event_urls_custom(event):
    custom = "https://foo.bar.com"
    assert custom not in event.urls.submit.full()
    event.custom_domain = custom
    assert custom in event.urls.submit.full()
    assert custom not in event.orga_urls.cfp.full()


@pytest.mark.django_db
def test_event_model_talks(
    slot, other_slot, accepted_submission, submission, rejected_submission
):
    event = slot.submission.event
    with scope(event=event):
        other_slot.submission.speakers.add(slot.submission.speakers.first())
        assert len(event.talks.all()) == len(set(event.talks.all()))
        assert len(event.speakers.all()) == len(set(event.speakers.all()))


@pytest.mark.django_db
def test_shred_used_event(
    resource,
    answered_choice_question,
    personal_answer,
    rejected_submission,
    deleted_submission,
    mail,
    sent_mail,
    room_availability,
    slot,
    unreleased_slot,
    past_slot,
    feedback,
    canceled_talk,
    review,
    information,
    other_event,
    track,
):
    rejected_submission.track = track
    rejected_submission.save()
    assert Event.objects.count() == 2
    rejected_submission.event.organiser.shred()
    assert Event.objects.count() == 1


@pytest.mark.django_db
def test_enable_plugin_twice(event):
    event.enable_plugin("test")
    event.enable_plugin("test")
    assert event.plugin_list == ["test"]


@pytest.mark.django_db
def test_disable_wrong_plugin(event):
    event.disable_plugin("teeeeeeeeeeest")
    assert event.plugin_list == []


@pytest.mark.django_db
def test_event_create_review_phase(event):
    with scope(event=event):
        event.review_phases.all().delete()
        assert event.active_review_phase


@pytest.mark.django_db
def test_event_update_review_phase_keep_outdated_phase(event):
    with scope(event=event):
        event.review_phases.all().delete()
        active_phase = event.active_review_phase
        active_phase.end = now() - dt.timedelta(days=3)
        active_phase.save()
        assert event.update_review_phase() == active_phase


@pytest.mark.django_db
def test_event_update_review_phase_activate_next_phase(event):
    from pretalx.submission.models.review import ReviewPhase

    with scope(event=event):
        event.review_phases.all().delete()
        active_phase = event.active_review_phase
        active_phase.end = now() - dt.timedelta(days=3)
        active_phase.save()
        new_phase = ReviewPhase.objects.create(
            event=event, position=3, start=active_phase.end
        )
        assert event.update_review_phase() == new_phase
