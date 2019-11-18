from datetime import timedelta
from urllib.parse import urlparse

import bs4
import django.forms as forms
import pytest
from django.core import mail as djmail
from django.http.request import QueryDict
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from pretalx.submission.forms import InfoForm
from pretalx.submission.models import Submission, SubmissionType


class TestWizard:

    @staticmethod
    def get_response_and_url(client, url, follow=True, method='POST', data=None):
        if method == 'GET':
            response = client.get(url, follow=follow, data=data)
        else:
            response = client.post(url, follow=follow, data=data)
        try:
            current_url = response.redirect_chain[-1][0]
        except IndexError:  # We are not being redirected at all!
            current_url = url
        return response, current_url

    def perform_init_wizard(self, client, success=True, event=None, access_code=None):
        # Start wizard
        djmail.outbox = []
        url = '/test/submit/'
        if access_code:
            url += f'?access_code={access_code.code}'
        response, current_url = self.get_response_and_url(client, url, method='GET')
        assert ('/info/' in current_url) is success
        return response, current_url

    def perform_info_wizard(
        self,
        client,
        response,
        url,
        next_step='questions',
        title='Submission title',
        content_locale='en',
        description='Description',
        abstract='Abstract',
        notes='Notes',
        slot_count=1,
        submission_type=None,
        event=None,
        track=None,
        additional_speaker=None,
    ):
        submission_data = {
            'title': title,
            'content_locale': content_locale,
            'description': description,
            'abstract': abstract,
            'notes': notes,
            'slot_count': slot_count,
            'submission_type': submission_type,
            'additional_speaker': additional_speaker or '',
        }
        if track:
            submission_data['track'] = getattr(track, 'pk', track)
        response, current_url = self.get_response_and_url(
            client, url, data=submission_data
        )
        assert f'/{next_step}/' in current_url, f'{current_url} does not end with /{next_step}/!'
        return response, current_url

    def perform_question_wizard(self, client, response, url, data, next_step='profile', event=None):
        response, current_url = self.get_response_and_url(client, url, data=data)
        assert f'/{next_step}/' in current_url, f'{current_url} does not end with /{next_step}/!'
        return response, current_url

    def perform_user_wizard(
        self,
        client,
        response,
        url,
        password,
        next_step='profile',
        email=None,
        register=False,
        event=None,
    ):
        if register:
            data = {
                'register_name': email,
                'register_email': email,
                'register_password': password,
                'register_password_repeat': password,
            }
        else:
            data = {'login_email': email, 'login_password': password}
        response, current_url = self.get_response_and_url(client, url, data=data)
        assert f'/{next_step}/' in current_url, f'{current_url} does not end with /{next_step}/!'
        return response, current_url

    def perform_profile_form(
        self,
        client,
        response,
        url,
        name='Jane Doe',
        bio='l337 hax0r',
        next_step='me/submissions',
        event=None,
        success=True,
    ):
        data = {'name': name, 'biography': bio}
        response, current_url = self.get_response_and_url(client, url, data=data)
        assert f'/{next_step}/' in current_url, f'{current_url} does not end with /{next_step}/!'
        doc = bs4.BeautifulSoup(response.rendered_content, "lxml")
        if success:
            assert doc.select('.alert-success')
            assert doc.select('#user-dropdown-label')
        else:
            assert not doc.select('.alert-success')
            assert not doc.select('#user-dropdown-label')
        return response, current_url

    def assert_submission(
        self,
        event,
        title='Submission title',
        content_locale='en',
        description='Description',
        abstract='Abstract',
        notes='Notes',
        question=None,
        answer='42',
        track=None,
    ):
        with scope(event=event):
            sub = Submission.objects.last()
            assert sub.title == title
            assert sub.submission_type is not None
            assert sub.content_locale == content_locale
            assert sub.description == description
            assert sub.abstract == abstract
            assert sub.notes == notes
            assert sub.slot_count == 1
            if question:
                answ = sub.answers.first()
                assert answ
                assert answ.question == question
                assert answ.answer == answer
            else:
                assert sub.answers.count() == 0
            if track:
                assert sub.track == track
            else:
                assert sub.track is None
        return sub

    def assert_user(
        self,
        submission,
        email='testuser@example.com',
        name='Jane Doe',
        biography='l337 hax0r',
        question=None,
        answer=None,
    ):
        with scope(event=submission.event):
            user = submission.speakers.get(email=email)
            assert user.name == name
            assert user.profiles.get(event=submission.event).biography == biography
            if question:
                answ = user.answers.filter(question__target='speaker').first()
                assert answ
                assert answ.question == question
                assert answ.person == user
                assert not answ.submission
                assert answ.answer == 'green'
        return user

    def assert_mail(self, submission, user, count=1, extra=None):
        assert len(djmail.outbox) == count
        mail = djmail.outbox[0 if not extra else 1]
        assert submission.title in mail.subject
        assert submission.title in mail.body
        assert user.email in mail.to
        if extra:
            assert djmail.outbox[0].to == [extra]

    @pytest.mark.django_db
    def test_info_wizard_query_string_handling(self, event, client, track):
        # build query string
        params_dict = QueryDict(f'track={track.pk}&submission_type=academic_talk')
        current_url = '/test/submit/?{params_dict}'
        # Start wizard
        _, current_url = self.get_response_and_url(
            client, current_url, method='GET'
        )
        # get query string from current URL
        url_parts = urlparse(current_url)
        q = QueryDict(url_parts.query)
        assert url_parts.path.endswith('/info/') is True
        assert q.get('track') == params_dict.get('academic')
        assert q.get('submission_type') == params_dict.get('academic_talk')

    @pytest.mark.django_db
    def test_wizard_new_user(self, event, question, client):
        event.settings.set('mail_on_new_submission', True)
        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first().pk
        answer_data = {f'question_{question.pk}': '42'}

        response, current_url = self.perform_init_wizard(client, event=event)
        response, current_url = self.perform_info_wizard(
            client, response, current_url + '?submission_type={}-helpful-slug'.format(submission_type),
            submission_type=submission_type, event=event,
        )
        response, current_url = self.perform_question_wizard(
            client, response, current_url, answer_data, next_step='user',
            event=event
        )
        response, current_url = self.perform_user_wizard(
            client,
            response,
            current_url,
            password='testpassw0rd!',
            email='testuser@example.org',
            register=True,
            event=event,
        )
        response, current_url = self.perform_profile_form(client, response, current_url, event=event)
        submission = self.assert_submission(event, question=question)
        self.assert_user(submission, email='testuser@example.org')
        assert len(djmail.outbox) == 2  # user email plus orga email

    @pytest.mark.django_db
    def test_wizard_existing_user(
        self,
        event,
        client,
        question,
        user,
        speaker_question,
        choice_question,
        multiple_choice_question,
    ):
        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first().pk
            answer_data = {
                f'question_{question.pk}': '42',
                f'question_{speaker_question.pk}': 'green',
                f'question_{choice_question.pk}': choice_question.options.first().pk,
                f'question_{multiple_choice_question.pk}': multiple_choice_question.options.first().pk,
            }

        response, current_url = self.perform_init_wizard(client, event=event)
        response, current_url = self.perform_info_wizard(
            client, response, current_url + '?submission_type=123-helpful-slug', submission_type=submission_type,
            event=event,
        )
        response, current_url = self.perform_question_wizard(
            client, response, current_url, answer_data, next_step='user',
            event=event,
        )
        response, current_url = self.perform_user_wizard(
            client, response, current_url, email=user.email, password='testpassw0rd!',
            event=event,
        )
        response, current_url = self.perform_profile_form(client, response, current_url, event=event)

        submission = self.assert_submission(event, question=question)
        user = self.assert_user(submission, question=speaker_question, answer='green')
        self.assert_mail(submission, user)

    @pytest.mark.django_db
    def test_wizard_logged_in_user(
        self, event, client, question, user, review_question
    ):
        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first().pk
            answer_data = {f'question_{question.pk}': '42'}

        client.force_login(user)
        response, current_url = self.perform_init_wizard(client, event=event)
        response, current_url = self.perform_info_wizard(
            client, response, current_url, submission_type=submission_type,
            event=event,
        )
        response, current_url = self.perform_question_wizard(
            client, response, current_url, answer_data,
            event=event,
        )
        response, current_url = self.perform_profile_form(client, response, current_url, event=event)
        submission = self.assert_submission(event, question=question)
        user = self.assert_user(submission)
        self.assert_mail(submission, user)

    @pytest.mark.django_db
    def test_wizard_logged_in_user_no_questions(self, event, client, user):
        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first().pk

        client.force_login(user)
        response, current_url = self.perform_init_wizard(client, event=event)
        response, current_url = self.perform_info_wizard(
            client,
            response,
            current_url,
            submission_type=submission_type,
            next_step='profile',
            event=event,
            additional_speaker='additional@example.org',
        )
        response, current_url = self.perform_profile_form(client, response, current_url, event=event)
        submission = self.assert_submission(event)
        user = self.assert_user(submission)
        self.assert_mail(submission, user, extra='additional@example.org', count=2)

    @pytest.mark.django_db
    def test_wizard_logged_in_user_only_review_questions(
        self, event, client, user, review_question
    ):
        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first().pk

        client.force_login(user)
        response, current_url = self.perform_init_wizard(client, event=event)
        response, current_url = self.perform_info_wizard(
            client,
            response,
            current_url,
            submission_type=submission_type,
            next_step='profile',
            event=event
        )
        response, current_url = self.perform_profile_form(client, response, current_url, event=event)
        submission = self.assert_submission(event)
        user = self.assert_user(submission)
        self.assert_mail(submission, user)

    @pytest.mark.django_db
    def test_wizard_logged_in_user_no_questions_broken_template(
        self, event, client, user
    ):
        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first().pk

            event.ack_template.text = (
                str(event.ack_template.text) + '{name} and {nonexistent}'
            )
            event.ack_template.save()

        client.force_login(user)
        response, current_url = self.perform_init_wizard(client, event=event)
        response, current_url = self.perform_info_wizard(
            client,
            response,
            current_url,
            submission_type=submission_type,
            next_step='profile',
            event=event,
        )
        response, current_url = self.perform_profile_form(client, response, current_url, event=event)
        submission = self.assert_submission(event)
        user = self.assert_user(submission)
        assert len(djmail.outbox) == 0

    @pytest.mark.django_db
    def test_wizard_with_tracks(self, event, client, track, other_track):
        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first().pk
            event.settings.cfp_request_track = True
            event.settings.cfp_require_track = True

        response, current_url = self.perform_init_wizard(client, event=event)
        response, current_url = self.perform_info_wizard(
            client,
            response,
            current_url,
            submission_type=submission_type,
            next_step='user',
            event=event,
            track=track,
        )
        response, current_url = self.perform_user_wizard(
            client,
            response,
            current_url,
            password='testpassw0rd!',
            email='testuser@example.org',
            register=True,
            event=event,
        )
        response, current_url = self.perform_profile_form(client, response, current_url, event=event)
        submission = self.assert_submission(event, track=track)
        user = self.assert_user(submission, email='testuser@example.org')
        self.assert_mail(submission, user)

    @pytest.mark.django_db
    def test_wizard_cfp_closed(self, event, client, user):
        event.cfp.deadline = now() - timedelta(days=1)
        event.cfp.save()
        client.force_login(user)
        self.perform_init_wizard(client, success=False, event=event)

    @pytest.mark.django_db
    def test_wizard_cfp_closed_access_code(self, event, client, access_code):
        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first().pk
        event.cfp.deadline = now() - timedelta(days=1)
        event.cfp.save()
        response, current_url = self.perform_init_wizard(client, event=event, access_code=access_code)
        response, current_url = self.perform_info_wizard(
            client, response, current_url,
            submission_type=submission_type, event=event,
            next_step='user',
        )
        response, current_url = self.perform_user_wizard(
            client,
            response,
            current_url,
            password='testpassw0rd!',
            email='testuser@example.org',
            register=True,
            event=event,
        )
        response, current_url = self.perform_profile_form(client, response, current_url, event=event)
        submission = self.assert_submission(event)
        assert submission.access_code == access_code

    @pytest.mark.django_db
    def test_wizard_cfp_closed_expired_access_code(self, event, client, access_code):
        event.cfp.deadline = now() - timedelta(days=1)
        event.cfp.save()
        access_code.valid_until = now() - timedelta(hours=1)
        access_code.save()
        response, current_url = self.perform_init_wizard(client, event=event, access_code=access_code, success=False)

    @pytest.mark.django_db
    def test_wizard_track_access_code(self, event, client, access_code, track, other_track):
        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first().pk
            event.settings.cfp_request_track = True
            event.settings.cfp_require_track = True
            track.requires_access_code = True
            track.save()
            other_track.requires_access_code = True
            other_track.save()
            access_code.track = track
            access_code.save()

        response, current_url = self.perform_init_wizard(client, event=event)
        self.perform_info_wizard(  # Does not work without token
            client,
            response,
            current_url,
            submission_type=submission_type,
            next_step='info',
            event=event,
            track=track,
        )
        self.perform_info_wizard(  # Does not work with token, because wrong track
            client,
            response,
            current_url + '?access_code=' + access_code.code,
            submission_type=submission_type,
            next_step='info',
            event=event,
            track=other_track,
        )
        response, current_url = self.perform_info_wizard(  # Works with token and right track
            client,
            response,
            current_url + '?access_code=' + access_code.code,
            submission_type=submission_type,
            next_step='user',
            event=event,
            track=track,
        )
        response, current_url = self.perform_user_wizard(
            client,
            response,
            current_url,
            password='testpassw0rd!',
            email='testuser@example.org',
            register=True,
            event=event,
        )
        response, current_url = self.perform_profile_form(client, response, current_url, event=event)
        self.assert_submission(event, track=track)

    @pytest.mark.django_db
    def test_wizard_submission_type_access_code(self, event, client, access_code):
        with scope(event=event):
            submission_type = SubmissionType.objects.filter(event=event).first()
            submission_type.requires_access_code = True
            submission_type.save()
            submission_type = submission_type.pk

        response, current_url = self.perform_init_wizard(client, event=event)
        response, current_url = self.perform_info_wizard(  # Does not work without access token
            client,
            response,
            current_url,
            submission_type=submission_type,
            next_step='info',
            event=event,
        )
        response, current_url = self.perform_info_wizard(
            client,
            response,
            current_url + '?access_code=' + access_code.code,
            submission_type=submission_type,
            next_step='user',
            event=event,
        )
        response, current_url = self.perform_user_wizard(
            client,
            response,
            current_url,
            password='testpassw0rd!',
            email='testuser@example.org',
            register=True,
            event=event,
        )
        response, current_url = self.perform_profile_form(client, response, current_url, event=event)
        self.assert_submission(event)

    @pytest.mark.django_db
    def test_wizard_request_missing_step(self, event, client):
        _, current_url = self.perform_init_wizard(client, event=event)
        response = client.get(current_url.replace('info', 'wrooooong'))
        assert response.status_code == 404


@pytest.mark.django_db
def test_infoform_set_submission_type(event, other_event):
    # https://github.com/pretalx/pretalx/issues/642
    with scopes_disabled():
        assert len(SubmissionType.objects.all()) > 1
    with scope(event=event):
        f = InfoForm(event)
        assert len(event.submission_types.all()) == 1
        assert len(f.fields['submission_type'].queryset) == 1
        assert f.fields['submission_type'].initial == event.submission_types.all()[0]
        assert isinstance(f.fields['submission_type'].widget, forms.HiddenInput)


@pytest.mark.django_db
def test_infoform_set_submission_type_2nd_event(event, other_event, submission_type):
    # https://github.com/pretalx/pretalx/issues/642
    with scopes_disabled():
        assert len(SubmissionType.objects.all()) > 1
    with scope(event=event):
        f = InfoForm(event)
        assert len(event.submission_types.all()) == 2
        assert len(f.fields['submission_type'].queryset) == 2
        assert not isinstance(f.fields['submission_type'].widget, forms.HiddenInput)
