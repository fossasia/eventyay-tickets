import bs4
import pytest

from pretalx.submission.models import Submission, SubmissionType


@pytest.mark.django_db
def test_wizard_new_user(event, question, client):
    # Start wizard
    resp = client.get('/test/submit/', follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/info/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit first form
    data = {
        'info-title': 'Submission title',
        'info-submission_type': SubmissionType.objects.filter(event=event).first().pk,
        'info-content_locale': 'en',
        'info-description': 'Description',
        'info-abstract': 'Abstract',
        'info-notes': 'Notes',
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/questions/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit question form
    data = {
        'questions-question_' + str(question.pk): '42',
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/user/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit user form
    data = {
        'user-register_username': 'testuser',
        'user-register_email': 'testuser@example.org',
        'user-register_password': 'testpassw0rd',
        'user-register_password_repeat': 'testpassw0rd',
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/profile/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit profile form
    data = {
        'profile-name': 'John Doe',
        'profile-biography': 'I\'m awesome',
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/me/submissions')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")
    assert doc.select('.alert-success')
    assert doc.select('.user-row')

    sub = Submission.objects.last()
    assert sub.title == 'Submission title'
    assert sub.submission_type is not None
    assert sub.content_locale == 'en'
    assert sub.description == 'Description'
    assert sub.abstract == 'Abstract'
    assert sub.notes == 'Notes'
    answ = sub.answers.first()
    assert answ.question == question
    assert answ.answer == '42'
    user = sub.speakers.first()
    assert user.nick == 'testuser'
    assert user.email == 'testuser@example.org'
    assert user.name == 'John Doe'
    assert user.profiles.get(event=event).biography == 'I\'m awesome'


@pytest.mark.django_db
def test_wizard_existing_user(event, client, question, user):
    # Start wizard
    resp = client.get('/test/submit/', follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/info/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit first form
    data = {
        'info-title': 'Submission title',
        'info-submission_type': SubmissionType.objects.filter(event=event).first().pk,
        'info-content_locale': 'en',
        'info-description': 'Description',
        'info-abstract': 'Abstract',
        'info-notes': 'Notes',
        'info-duration': '45'
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/questions/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit question form
    data = {
        'questions-question_' + str(question.pk): '42',
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/user/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit user form
    data = {
        'user-login_username': 'testuser',
        'user-login_password': 'testpassw0rd',
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/profile/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit profile form
    data = {
        'profile-name': 'John Doe',
        'profile-biography': 'I\'m awesome',
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/me/submissions')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")
    assert doc.select('.alert-success')
    assert doc.select('.user-row')

    sub = Submission.objects.last()
    assert sub.title == 'Submission title'
    answ = sub.answers.first()
    assert answ.question == question
    assert answ.answer == '42'
    s_user = sub.speakers.first()
    assert s_user.pk == user.pk
    assert s_user.nick == 'testuser'
    assert s_user.name == 'John Doe'
    assert s_user.profiles.get(event=event).biography == 'I\'m awesome'


@pytest.mark.django_db
def test_wizard_logged_in_user(event, client, question, user):
    client.force_login(user)

    # Start wizard
    resp = client.get('/test/submit/', follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/info/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit first form
    data = {
        'info-title': 'Submission title',
        'info-submission_type': SubmissionType.objects.filter(event=event).first().pk,
        'info-content_locale': 'en',
        'info-description': 'Description',
        'info-abstract': 'Abstract',
        'info-notes': 'Notes',
        'info-duration': '45'
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/questions/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit question form
    data = {
        'questions-question_' + str(question.pk): '42',
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/profile/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit profile form
    data = {
        'profile-name': 'John Doe',
        'profile-biography': 'I\'m awesome',
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/me/submissions')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")
    assert doc.select('.alert-success')
    assert doc.select('.user-row')

    sub = Submission.objects.last()
    assert sub.title == 'Submission title'
    answ = sub.answers.first()
    assert answ.question == question
    assert answ.answer == '42'
    s_user = sub.speakers.first()
    assert s_user.pk == user.pk
    assert s_user.nick == 'testuser'
    assert s_user.name == 'John Doe'
    assert s_user.profiles.get(event=event).biography == 'I\'m awesome'


@pytest.mark.django_db
def test_wizard_logged_in_user_no_questions(event, client, user):
    client.force_login(user)

    # Start wizard
    resp = client.get('/test/submit/', follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/info/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit first form
    data = {
        'info-title': 'Submission title',
        'info-submission_type': SubmissionType.objects.filter(event=event).first().pk,
        'info-content_locale': 'en',
        'info-description': 'Description',
        'info-abstract': 'Abstract',
        'info-notes': 'Notes',
        'info-duration': '45'
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/profile/')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")

    # Submit profile form
    data = {
        'profile-name': 'John Doe',
        'profile-biography': 'I\'m awesome',
    }
    inp_hidden = doc.select("input[name^=submit_wizard]")[0]
    data[inp_hidden['name']] = inp_hidden['value']

    resp = client.post(current_url, data, follow=True)
    current_url = resp.redirect_chain[-1][0]
    assert current_url.endswith('/me/submissions')
    doc = bs4.BeautifulSoup(resp.rendered_content, "lxml")
    assert doc.select('.alert-success')
    assert doc.select('.user-row')

    sub = Submission.objects.last()
    assert sub.title == 'Submission title'
    assert not sub.answers.exists()
    s_user = sub.speakers.first()
    assert s_user.pk == user.pk
    assert s_user.nick == 'testuser'
    assert s_user.name == 'John Doe'
    assert s_user.profiles.get(event=event).biography == 'I\'m awesome'


# TODO: test failed registration
# TODO: test failed login
# TODO: test required fields
# TODO: test required questions
