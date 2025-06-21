import pytest
from django_scopes import scope
from selenium.webdriver.common.by import By

from .utils import screenshot


@pytest.mark.django_db
def screenshot_agenda_public_schedule(live_server, client, event):
    with scope(event=event):
        client.get(live_server.url + f"/{event.slug}/schedule/")
    screenshot(client, "website/agenda_public.png")


@pytest.mark.django_db
def screenshot_cfp_submission_info(live_server, client, event):
    client.set_window_size(400, 100)
    with scope(event=event):
        client.get(live_server.url + f"/{event.slug}/submit/423mOn/info/")
    screenshot(client, "website/cfp_start.png")


@pytest.mark.django_db
def screenshot_cfp_submission_questions(live_server, client, event):
    with scope(event=event):
        client.get(live_server.url + f"/{event.slug}/submit/423mOn/questions/")
    screenshot(client, "website/cfp_questions.png")


@pytest.mark.django_db
def screenshot_edit_cfp_settings(live_server, logged_in_client, event):
    logged_in_client.set_window_size(1000, 1000)
    with scope(event=event):
        logged_in_client.get(
            live_server.url + f"/orga/event/{event.slug}/cfp/text#tab-fields"
        )
        logged_in_client.execute_script("window.scrollBy(0, 950)")
    screenshot(logged_in_client, "website/cfp_settings.png")


@pytest.mark.django_db
def screenshot_edit_question_settings(live_server, logged_in_client, event):
    with scope(event=event):
        logged_in_client.get(
            live_server.url + f"/orga/event/{event.slug}/cfp/questions/new"
        )
        logged_in_client.find_element(By.CSS_SELECTOR, "#id_variant").click()
    screenshot(logged_in_client, "website/question_settings.png")


@pytest.mark.django_db
def screenshot_edit_mail_templates(live_server, logged_in_client, event):
    with scope(event=event):
        logged_in_client.get(
            live_server.url + f"/orga/event/{event.slug}/mails/templates"
        )
    screenshot(logged_in_client, "website/mail_templates.png")


@pytest.mark.django_db
def screenshot_review_submission(live_server, logged_in_client, event):
    with scope(event=event):
        submission = event.submissions.first()
        logged_in_client.get(
            live_server.url
            + "/orga/event/{}/submissions/{}/reviews".format(
                event.slug, submission.code
            )
        )
    screenshot(logged_in_client, "website/review_submission.png")
