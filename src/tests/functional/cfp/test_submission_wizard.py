import bs4
import pytest
from django.core import mail as djmail

from pretalx.submission.models import Submission, SubmissionType


class TestWizard:

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

    def perform_init_wizard(self, client):
        # Start wizard
        djmail.outbox = []
        response, current_url = self.get_response_and_url(client, '/test/submit/', method='GET')
        assert current_url.endswith('/info/')
        return response, current_url

    def perform_info_wizard(
        self, client, response, url, next='questions',
        title='Submission title', content_locale='en', description='Description',
        abstract='Abstract', notes='Notes', submission_type=None,
    ):
        submission_data = {
            'info-title': title, 'info-content_locale': content_locale,
            'info-description': description, 'info-abstract': abstract,
            'info-notes': notes, 'info-submission_type': submission_type,
        }
        key, value = self.get_form_name(response)
        submission_data[key] = value
        response, current_url = self.get_response_and_url(client, url, data=submission_data)
        assert current_url.endswith(f'/{next}/')
        return response, current_url

    def perform_question_wizard(self, client, response, url, data, next='profile'):
        key, value = self.get_form_name(response)
        data[key] = value
        response, current_url = self.get_response_and_url(client, url, data=data)
        assert current_url.endswith(f'/{next}/')
        return response, current_url

    def perform_user_wizard(self, client, response, url, username, password, next='profile', email=None, register=False):
        if register:
            data = {
                'user-register_username': username,
                'user-register_email': email,
                'user-register_password': password,
                'user-register_password_repeat': password,
            }
        else:
            data = {
                'user-login_username': username,
                'user-login_password': password,
            }
        key, value = self.get_form_name(response)
        data[key] = value
        response, current_url = self.get_response_and_url(client, url, data=data)
        assert current_url.endswith(f'/{next}/')
        return response, current_url

    def perform_profile_form(self, client, response, url, name='Jane Doe', bio='l337 hax0r', next='/me/submissions'):
        data = {
            'profile-name': name,
            'profile-biography': bio,
        }
        key, value = self.get_form_name(response)
        data[key] = value
        response, current_url = self.get_response_and_url(client, url, data=data)
        assert current_url.endswith(next)
        return response, current_url

    @pytest.mark.django_db
    def test_wizard_new_user(self, event, question, client):
        event.settings.set('mail_on_new_submission', True)
        submission_type = SubmissionType.objects.filter(event=event).first().pk
        answer_data = {f'questions-question_{question.pk}': '42', }

        response, current_url = self.perform_init_wizard(client)
        response, current_url = self.perform_info_wizard(client, response, current_url, submission_type=submission_type)
        response, current_url = self.perform_question_wizard(client, response, current_url, answer_data, next='user')
        response, current_url = self.perform_user_wizard(client, response, current_url, username='testuser', password='testpassw0rd!', email='testuser@example.org', register=True)
        response, current_url = self.perform_profile_form(client, response, current_url)

        doc = bs4.BeautifulSoup(response.rendered_content, "lxml")
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
        assert user.name == 'Jane Doe'
        assert user.profiles.get(event=event).biography == 'l337 hax0r'
        assert len(djmail.outbox) == 2  # user email plus orga email

    @pytest.mark.django_db
    def test_wizard_existing_user(self, event, client, question, user, speaker_question, choice_question, multiple_choice_question):
        submission_type = SubmissionType.objects.filter(event=event).first().pk
        answer_data = {
            f'questions-question_{question.pk}': '42',
            f'questions-question_{speaker_question.pk}': 'green',
            f'questions-question_{choice_question.pk}': choice_question.options.first().pk,
            f'questions-question_{multiple_choice_question.pk}': multiple_choice_question.options.first().pk,
        }

        response, current_url = self.perform_init_wizard(client)
        response, current_url = self.perform_info_wizard(client, response, current_url, submission_type=submission_type)
        response, current_url = self.perform_question_wizard(client, response, current_url, answer_data, next='user')
        response, current_url = self.perform_user_wizard(client, response, current_url, username='testuser', password='testpassw0rd!')
        response, current_url = self.perform_profile_form(client, response, current_url)

        doc = bs4.BeautifulSoup(response.rendered_content, "lxml")
        assert doc.select('.alert-success')
        assert doc.select('.user-row')

        sub = Submission.objects.last()
        assert sub.title == 'Submission title'
        answ = sub.answers.filter(question__target='submission').first()
        assert answ.question == question
        assert answ.answer == '42'
        assert answ.submission == sub
        assert not answ.person
        answ = user.answers.filter(question__target='speaker').first()
        assert answ.question == speaker_question
        assert answ.person == user
        assert not answ.submission
        assert answ.answer == 'green'
        s_user = sub.speakers.first()
        assert s_user.pk == user.pk
        assert s_user.nick == 'testuser'
        assert s_user.name == 'Jane Doe'
        assert s_user.profiles.get(event=event).biography == 'l337 hax0r'
        assert len(djmail.outbox) == 1

    @pytest.mark.django_db
    def test_wizard_logged_in_user(self, event, client, question, user):
        submission_type = SubmissionType.objects.filter(event=event).first().pk
        answer_data = {f'questions-question_{question.pk}': '42', }

        client.force_login(user)
        response, current_url = self.perform_init_wizard(client)
        response, current_url = self.perform_info_wizard(client, response, current_url, submission_type=submission_type)
        response, current_url = self.perform_question_wizard(client, response, current_url, answer_data, next='profile')
        response, current_url = self.perform_profile_form(client, response, current_url)

        doc = bs4.BeautifulSoup(response.rendered_content, "lxml")
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
        assert s_user.name == 'Jane Doe'
        assert s_user.profiles.get(event=event).biography == 'l337 hax0r'
        assert len(djmail.outbox) == 1

    @pytest.mark.django_db
    def test_wizard_logged_in_user_no_questions(self, event, client, user):
        submission_type = SubmissionType.objects.filter(event=event).first().pk

        client.force_login(user)
        response, current_url = self.perform_init_wizard(client)
        response, current_url = self.perform_info_wizard(client, response, current_url, submission_type=submission_type, next='profile')
        response, current_url = self.perform_profile_form(client, response, current_url)

        doc = bs4.BeautifulSoup(response.rendered_content, "lxml")
        assert doc.select('.alert-success')
        assert doc.select('.user-row')
        sub = Submission.objects.last()
        assert sub.title == 'Submission title'
        assert not sub.answers.exists()
        s_user = sub.speakers.first()
        assert s_user.pk == user.pk
        assert s_user.nick == 'testuser'
        assert s_user.name == 'Jane Doe'
        assert s_user.profiles.get(event=event).biography == 'l337 hax0r'
        assert len(djmail.outbox) == 1

    @pytest.mark.django_db
    def test_wizard_logged_in_user_no_questions_broken_template(self, event, client, user):
        submission_type = SubmissionType.objects.filter(event=event).first().pk

        event.ack_template.text = str(event.ack_template.text) + '{name} and {nonexistent}'
        event.ack_template.save()

        client.force_login(user)
        response, current_url = self.perform_init_wizard(client)
        response, current_url = self.perform_info_wizard(client, response, current_url, submission_type=submission_type, next='profile')
        response, current_url = self.perform_profile_form(client, response, current_url)

        doc = bs4.BeautifulSoup(response.rendered_content, "lxml")
        assert doc.select('.alert-success')
        assert doc.select('.user-row')
        sub = Submission.objects.last()
        assert sub.title == 'Submission title'
        assert not sub.answers.exists()
        s_user = sub.speakers.first()
        assert s_user.pk == user.pk
        assert s_user.nick == 'testuser'
        assert s_user.name == 'Jane Doe'
        assert s_user.profiles.get(event=event).biography == 'l337 hax0r'
        assert len(djmail.outbox) == 0


# TODO: test failed registration
# TODO: test failed login
# TODO: test required fields
# TODO: test required questions
