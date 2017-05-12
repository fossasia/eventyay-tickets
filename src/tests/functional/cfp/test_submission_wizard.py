import copy

import bs4
import pytest

from pretalx.submission.models import Submission, SubmissionType


class TestWizard:
    submission_data = {
        'info-title': 'Submission title',
        'info-content_locale': 'en',
        'info-description': 'Description',
        'info-abstract': 'Abstract',
        'info-notes': 'Notes',
    }
    profile_data = {
        'profile-name': 'John Doe',
        'profile-biography': 'I\'m awesome',
    }

    def get_response_and_url(self, client, url, follow=True, method='POST', data=None):
        if method == 'GET':
            response = client.get(url, follow=follow, data=data)
        elif method == 'POST':
            response = client.post(url, follow=follow, data=data)
        current_url = response.redirect_chain[-1][0]
        return response, current_url

    def get_form_name(self, response):
        doc = bs4.BeautifulSoup(response.rendered_content, "lxml")
        input_hidden = doc.select("input[name^=submit_wizard]")[0]
        return input_hidden['name'], input_hidden['value']

    @pytest.mark.django_db
    def test_wizard_new_user(self, event, question, client):
        # Start wizard
        resp, current_url = self.get_response_and_url(client, '/test/submit/', method='GET')
        assert current_url.endswith('/info/')

        # Submit info form
        data = copy.copy(self.submission_data)
        data['info-submission_type'] = SubmissionType.objects.filter(event=event).first().pk
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
        assert current_url.endswith('/questions/')

        # Submit question form
        data = {f'questions-question_{question.pk}': '42',}
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
        assert current_url.endswith('/user/')

        # Submit user form
        data = {
            'user-register_username': 'testuser',
            'user-register_email': 'testuser@example.org',
            'user-register_password': 'testpassw0rd',
            'user-register_password_repeat': 'testpassw0rd',
        }
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
        assert current_url.endswith('/profile/')

        # Submit profile form
        data = self.profile_data
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
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
    def test_wizard_existing_user(self, event, client, question, user):
        # Start wizard
        resp, current_url = self.get_response_and_url(client, '/test/submit/', method='GET')
        assert current_url.endswith('/info/')

        # Submit info form
        data = copy.copy(self.submission_data)
        data['info-submission_type'] = SubmissionType.objects.filter(event=event).first().pk
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
        assert current_url.endswith('/questions/')

        # Submit question form
        data = {f'questions-question_{question.pk}': '42',}
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
        assert current_url.endswith('/user/')

        # Submit user form
        data = {
            'user-login_username': 'testuser',
            'user-login_password': 'testpassw0rd',
        }
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
        assert current_url.endswith('/profile/')

        # Submit profile form
        data = self.profile_data
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
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
    def test_wizard_logged_in_user(self, event, client, question, user):
        client.force_login(user)

        # Start wizard
        resp, current_url = self.get_response_and_url(client, '/test/submit/', method='GET')
        assert current_url.endswith('/info/')

        # Submit info form
        data = copy.copy(self.submission_data)
        data['info-submission_type'] = SubmissionType.objects.filter(event=event).first().pk
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
        assert current_url.endswith('/questions/')

        # Submit question form
        data = {f'questions-question_{question.pk}': '42',}
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
        assert current_url.endswith('/profile/')

        # Submit profile form
        data = self.profile_data
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
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
    def test_wizard_logged_in_user_no_questions(self, event, client, user):
        client.force_login(user)

        # Start wizard
        resp, current_url = self.get_response_and_url(client, '/test/submit/', method='GET')
        assert current_url.endswith('/info/')

        # Submit info form
        data = copy.copy(self.submission_data)
        data['info-submission_type'] = SubmissionType.objects.filter(event=event).first().pk
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
        assert current_url.endswith('/profile/')

        # Submit profile form
        data = self.profile_data
        key, value = self.get_form_name(resp)
        data[key] = value
        resp, current_url = self.get_response_and_url(client, current_url, data=data)
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
