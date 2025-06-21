import datetime as dt
import random
from urllib.parse import urlparse

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db.models import F
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

SEED = random.randint(0, 100000)


@pytest.fixture
def chrome_options(chrome_options):
    chrome_options.add_argument("headless")
    chrome_options.add_argument("window-size=1600,1600")
    return chrome_options


@pytest.fixture(autouse=True)
def fix_settings(live_server):
    # Override the Django settings as to use the live_server fixture's URL
    settings.SITE_URL = live_server.url
    settings.SITE_NETLOC = urlparse(settings.SITE_URL).netloc


@pytest.fixture(autouse=True)
def event():
    from pretalx.common.models.settings import GlobalSettings
    from pretalx.event.models import Event
    from pretalx.person.models import User
    from pretalx.schedule.models import TalkSlot
    from pretalx.submission.models import AnswerOption, Question, QuestionVariant

    gs = GlobalSettings()
    gs.settings.update_check_result_warning = False
    gs.settings.update_check_ack = True
    User.objects.create_superuser(
        email="jane@example.org", name=_("Jane Doe"), locale="en", password="jane"
    )
    call_command("create_test_event", "--seed", str(SEED))
    event = Event.objects.last()
    with scope(event=event):
        event.name = "Meta Event Tech Alternative"
        event.is_public = True
        event.email = "orga@orga.org"
        event.date_from = dt.date.today()
        event.date_to = dt.date.today() + dt.timedelta(days=1)
        event.feature_flags["export_html_on_release"] = False
        event.display_settings["header_pattern"] = "topo"
        event.primary_color = "#3aa57c"
        event.save()
        assert event.submissions.count()
        assert event.slug == "democon"

        question = Question.objects.create(
            event=event,
            question="Which of these will you require for your presentation?",
            variant=QuestionVariant.MULTIPLE,
            target="submission",
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
        )
        event.cfp.deadline = now() + dt.timedelta(days=1, hours=8)
        event.cfp.save()
        TalkSlot.objects.all().filter(room__event=event).update(
            start=F("start") - dt.timedelta(days=5)
        )
        TalkSlot.objects.all().filter(room__event=event).update(
            end=F("end") - dt.timedelta(days=5)
        )
    call_command("collectstatic", "--noinput", "--clear")
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
    selenium.implicitly_wait(2)
    return selenium


@pytest.fixture
def logged_in_client(live_server, selenium, user):
    selenium.get(live_server.url + "/orga/login/")
    assert "Sign in" in selenium.title, selenium.title
    selenium.implicitly_wait(8)

    from selenium.webdriver.common.by import By

    selenium.find_element(By.CSS_SELECTOR, "form input[name=login_email]").send_keys(
        user.email
    )
    selenium.find_element(By.CSS_SELECTOR, "form input[name=login_password]").send_keys(
        "john"
    )
    selenium.find_element(By.CSS_SELECTOR, "form button[type=submit]").click()
    return selenium
