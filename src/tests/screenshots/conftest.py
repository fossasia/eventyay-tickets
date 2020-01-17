import datetime as dt
import random

import pytest
from django.core.management import call_command
from django.utils.translation import gettext as _
from django_scopes import scope

SEED = random.randint(0, 100000)


@pytest.fixture
def chrome_options(chrome_options):
    chrome_options.add_argument("headless")
    chrome_options.add_argument("window-size=1024x768")
    return chrome_options


@pytest.fixture(autouse=True)
def event():
    from pretalx.event.models import Event
    from pretalx.submission.models import Question, AnswerOption, QuestionVariant
    from pretalx.person.models import User

    User.objects.create_superuser(
        email="jane@example.org", name=_("Jane Doe"), locale="en", password="jane"
    )
    call_command("collectstatic", "--noinput", "--clear")
    call_command("create_test_event", "--seed", str(SEED))
    event = Event.objects.last()
    with scope(event=event):
        event.name = "Meta Event Tech Alternative"
        event.is_public = True
        event.email = "orga@orga.org"
        event.date_from = dt.date.today()
        event.date_to = dt.date.today() + dt.timedelta(days=1)
        event.settings.export_html_on_schedule_release = False
        event.settings.display_header_pattern = "topo"
        event.save()
        assert event.submissions.count()
        assert event.slug == "democon"

        question = Question.objects.create(
            event=event,
            question="Which of these will you require for your presentation?",
            variant=QuestionVariant.MULTIPLE,
            target="submission",
            required=False,
        )
        AnswerOption.objects.create(answer="Projector", question=question)
        AnswerOption.objects.create(answer="Sound playback", question=question)
        AnswerOption.objects.create(answer="Presentation laptop", question=question)
        AnswerOption.objects.create(answer="Laser pointer", question=question)
        AnswerOption.objects.create(answer="Assistant", question=question)

        Question.objects.create(
            event=event,
            question="Do you have dietary requirements?",
            variant=QuestionVariant.STRING,
            target="speaker",
            required=False,
        )
    return event


@pytest.fixture
def user(event):
    from pretalx.event.models import Team
    from pretalx.person.models import User

    team = Team.objects.create(
        name=_("Organisers"),
        organiser=event.organiser,
        can_create_events=True,
        can_change_teams=True,
        can_change_organiser_settings=True,
        can_change_event_settings=True,
        can_change_submissions=True,
        is_reviewer=True,
        all_events=True,
    )
    user = User.objects.create_user(
        email="john@example.org", name=_("John Doe"), locale="en", password="john"
    )
    team.members.add(user)
    return user


@pytest.fixture
def client(live_server, selenium, user):
    selenium.implicitly_wait(10)
    return selenium


@pytest.fixture
def logged_in_client(live_server, selenium, user):
    selenium.get(live_server.url + "/orga/login/")
    selenium.implicitly_wait(10)

    selenium.find_element_by_css_selector("form input[name=login_email]").send_keys(
        user.email
    )
    selenium.find_element_by_css_selector("form input[name=login_password]").send_keys(
        "john"
    )
    selenium.find_element_by_css_selector("form button[type=submit]").click()
    return selenium
