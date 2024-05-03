from datetime import timedelta
from doctest import DocTestSuite
from io import StringIO
import pickle
from threading import Thread
import unittest

from freezegun import freeze_time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection
from django.test import RequestFactory
from django.test import TestCase as DjangoTestCase
from django.test import TransactionTestCase as DjangoTransactionTestCase
from django.test import skipUnlessDBFeature
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from django_otp import (
    DEVICE_ID_SESSION_KEY,
    match_token,
    oath,
    user_has_device,
    util,
    verify_token,
)
from django_otp.forms import OTPTokenForm
from django_otp.middleware import OTPMiddleware
from django_otp.models import GenerateNotAllowed, VerifyNotAllowed
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()

    suite.addTests(tests)
    suite.addTest(DocTestSuite(util))
    suite.addTest(DocTestSuite(oath))

    return suite


class TestThread(Thread):
    "Django testing quirk: threads have to close their DB connections."

    def run(self):
        super().run()
        connection.close()


class OTPTestCaseMixin:
    """
    Utilities for dealing with custom user models.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.User = get_user_model()
        cls.USERNAME_FIELD = cls.User.USERNAME_FIELD

    def create_user(self, username, password, **kwargs):
        """
        Try to create a user, honoring the custom user model, if any.

        This may raise an exception if the user model is too exotic for our
        purposes.
        """
        return self.User.objects.create_user(username, password=password, **kwargs)


class TestCase(OTPTestCaseMixin, DjangoTestCase):
    pass


class TransactionTestCase(OTPTestCaseMixin, DjangoTransactionTestCase):
    pass


class TimestampTestMixin:
    """
    Generic tests for :class:`~django_otp.models.TimestampMixin`.

    Implementing tests must initialize `self.device` with the model instance to
    test and provide `valid_token` and `invalid_token` methods for verifying
    token behavior.

    Includes tests to:

    - Check automatic setting of `created_at` upon object creation.
    - Validate that `last_used_at` is initially None and updated only after
      successful token verification.
    - Ensure `set_last_used_timestamp` behaves correctly, respecting the
      `commit` parameter.

    """

    def setUp(self):
        self.device = None

    def valid_token(self):
        """Returns a valid token to pass to our device under test."""
        raise NotImplementedError()

    def invalid_token(self):
        """Returns an invalid token to pass to our device under test."""
        raise NotImplementedError()

    #
    # Tests
    #

    def test_created_at_set_on_creation(self):
        """Verify that the `created_at` field is automatically set upon creation."""
        self.assertIsNotNone(
            self.device.created_at, "created_at should be automatically set."
        )

    def test_last_used_at_initially_none(self):
        """Ensure `last_used_at` is None upon initial creation."""
        self.assertIsNone(
            self.device.last_used_at, "last_used_at should be None initially."
        )

    def test_set_last_used_timestamp_updates_field(self):
        """Check if `set_last_used_timestamp` correctly updates the `last_used_at` field."""
        self.device.set_last_used_timestamp(commit=True)
        self.device.refresh_from_db()  # Assuming it's a persisted model

        self.assertIsNotNone(
            self.device.last_used_at, "last_used_at should be updated."
        )

    def test_set_last_used_timestamp_without_commit(self):
        """
        Ensure `set_last_used_timestamp` updates `last_used_at` without persisting
        when commit=False.
        """
        original_last_used_at = self.device.last_used_at
        self.device.set_last_used_timestamp(commit=False)
        # Check in-memory update without saving
        self.assertNotEqual(
            self.device.last_used_at,
            original_last_used_at,
            "last_used_at should be updated in memory without commit.",
        )

        # Refresh from db to confirm it wasn't committed
        self.device.refresh_from_db()
        self.assertEqual(
            self.device.last_used_at,
            original_last_used_at,
            "last_used_at should not be updated in db without commit.",
        )

    def test_verify_token_successful_updates_last_used_at(self):
        """
        Verifying with a valid token updates 'last_used_at'.
        """
        valid_token = self.valid_token()  # Method to generate a valid token
        initial_last_used_at = self.device.last_used_at
        verified = self.device.verify_token(valid_token)

        self.assertTrue(verified, "Token should be verified successfully.")
        self.device.refresh_from_db()
        self.assertNotEqual(
            self.device.last_used_at,
            initial_last_used_at,
            "'last_used_at' should be updated on successful verification.",
        )

    def test_verify_token_failed_does_not_update_last_used_at(self):
        """
        Verifying with an invalid token does not update 'last_used_at'.
        """
        invalid_token = self.invalid_token()  # Method to generate an invalid token
        initial_last_used_at = self.device.last_used_at
        verified = self.device.verify_token(invalid_token)

        self.assertFalse(verified, "Token should not be verified.")
        self.device.refresh_from_db()
        self.assertEqual(
            self.device.last_used_at,
            initial_last_used_at,
            "'last_used_at' should not be updated on failed verification.",
        )


class ThrottlingTestMixin:
    """
    Generic tests for throttled devices.

    Any concrete device implementation that uses throttling should define a
    TestCase subclass that includes this as a base class. This will help verify
    a correct integration of ThrottlingMixin.

    Subclasses are responsible for populating self.device with a device to test
    as well as implementing methods to generate tokens to test with.

    """

    def setUp(self):
        self.device = None

    def valid_token(self):
        """Returns a valid token to pass to our device under test."""
        raise NotImplementedError()

    def invalid_token(self):
        """Returns an invalid token to pass to our device under test."""
        raise NotImplementedError()

    #
    # Tests
    #

    def test_delay_imposed_after_fail(self):
        verified1 = self.device.verify_token(self.invalid_token())
        self.assertFalse(verified1)
        verified2 = self.device.verify_token(self.valid_token())
        self.assertFalse(verified2)

    def test_delay_after_fail_expires(self):
        verified1 = self.device.verify_token(self.invalid_token())
        self.assertFalse(verified1)
        with freeze_time() as frozen_time:
            # With default settings initial delay is 1 second
            frozen_time.tick(delta=timedelta(seconds=1.1))
            verified2 = self.device.verify_token(self.valid_token())
            self.assertTrue(verified2)

    def test_throttling_failure_count(self):
        self.assertEqual(self.device.throttling_failure_count, 0)
        for i in range(0, 5):
            self.device.verify_token(self.invalid_token())
            # Only the first attempt will increase throttling_failure_count,
            # the others will all be within 1 second of first
            # and therefore not count as attempts.
            self.assertEqual(self.device.throttling_failure_count, 1)

    def test_verify_is_allowed(self):
        # Initially should be allowed
        verify_is_allowed1, data1 = self.device.verify_is_allowed()
        self.assertEqual(verify_is_allowed1, True)
        self.assertEqual(data1, None)

        # After failure, verify is not allowed
        with freeze_time():
            self.device.verify_token(self.invalid_token())
            verify_is_allowed2, data2 = self.device.verify_is_allowed()
            self.assertEqual(verify_is_allowed2, False)
            self.assertEqual(
                data2,
                {
                    'reason': VerifyNotAllowed.N_FAILED_ATTEMPTS,
                    'failure_count': 1,
                    'locked_until': timezone.now() + timezone.timedelta(seconds=1),
                },
            )

        # After a successful attempt, should be allowed again
        with freeze_time() as frozen_time:
            frozen_time.tick(delta=timedelta(seconds=1.1))
            self.device.verify_token(self.valid_token())

            verify_is_allowed3, data3 = self.device.verify_is_allowed()
            self.assertEqual(verify_is_allowed3, True)
            self.assertEqual(data3, None)


class CooldownTestMixin:
    def setUp(self):
        self.device = None

    def valid_token(self):
        """Returns a valid token to pass to our device under test."""
        raise NotImplementedError()

    def invalid_token(self):
        """Returns an invalid token to pass to our device under test."""
        raise NotImplementedError()

    #
    # Tests
    #

    def test_generate_is_allowed_on_first_try(self):
        """Token generation should be allowed on first try."""
        allowed, _ = self.device.generate_is_allowed()
        self.assertTrue(allowed)

    def test_cooldown_imposed_after_successful_generation(self):
        """
        Token generation before cooldown should not be allowed
        and the relevant reason should be returned.
        """
        with freeze_time():
            self.device.generate_challenge()
            self.device.refresh_from_db()
            allowed, details = self.device.generate_is_allowed()

            self.assertFalse(allowed)
            self.assertEqual(
                details['reason'], GenerateNotAllowed.COOLDOWN_DURATION_PENDING
            )

    def test_cooldown_expire_time(self):
        """
        When token generation is not allowed, the cooldown expire time
        should be returned.
        """
        with freeze_time():
            self.device.generate_challenge()
            self.device.refresh_from_db()
            _, details = self.device.generate_is_allowed()
            self.assertEqual(
                details['next_generation_at'], timezone.now() + timedelta(seconds=10)
            )

    def test_cooldown_reset(self):
        """Cooldown can be reset and allow token generation again before the initial period expires."""
        with freeze_time():
            self.device.generate_is_allowed()
            self.device.refresh_from_db()
            self.device.cooldown_reset()
            self.device.refresh_from_db()
            allowed, _ = self.device.generate_is_allowed()
            self.assertTrue(allowed)

    def test_valid_token_verification_resets_cooldown(self):
        """When the token is verified, the cooldown period is reset."""
        with freeze_time():
            self.device.generate_challenge()
            self.device.refresh_from_db()
            verified = self.device.verify_token(self.valid_token())
            self.assertTrue(verified)
            self.device.refresh_from_db()
            allowed, _ = self.device.generate_is_allowed()
            self.assertTrue(allowed)

    def test_invalid_token_verification_does_not_reset_cooldown(self):
        """When the token is not verified, the cooldown period is not reset."""
        with freeze_time():
            self.device.generate_challenge()
            self.device.refresh_from_db()
            verified = self.device.verify_token(self.invalid_token())
            self.assertFalse(verified)
            self.device.refresh_from_db()
            allowed, _ = self.device.generate_is_allowed()
            self.assertFalse(allowed)


@override_settings(OTP_STATIC_THROTTLE_FACTOR=0)
class APITestCase(TestCase):
    def setUp(self):
        try:
            self.alice = self.create_user('alice', 'password')
            self.bob = self.create_user('bob', 'password')
        except IntegrityError:
            self.skipTest("Unable to create a test user.")
        else:
            device = self.alice.staticdevice_set.create()
            device.token_set.create(token='alice')

    def test_user_has_device(self):
        with self.subTest(user='anonymous'):
            self.assertFalse(user_has_device(AnonymousUser()))
        with self.subTest(user='alice'):
            self.assertTrue(user_has_device(self.alice))
        with self.subTest(user='bob'):
            self.assertFalse(user_has_device(self.bob))

    def test_verify_token(self):
        device = self.alice.staticdevice_set.first()

        verified = verify_token(self.alice, device.persistent_id, 'bogus')
        self.assertIsNone(verified)

        verified = verify_token(self.alice, device.persistent_id, 'alice')
        self.assertIsNotNone(verified)

    def test_match_token(self):
        verified = match_token(self.alice, 'bogus')
        self.assertIsNone(verified)

        verified = match_token(self.alice, 'alice')
        self.assertEqual(verified, self.alice.staticdevice_set.first())


class OTPMiddlewareTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        try:
            self.alice = self.create_user('alice', 'password')
            self.bob = self.create_user('bob', 'password')
        except IntegrityError:
            self.skipTest("Unable to create a test user.")
        else:
            for user in [self.alice, self.bob]:
                device = user.staticdevice_set.create()
                device.token_set.create(token=user.get_username())

        self.middleware = OTPMiddleware(lambda r: None)

    def test_verified(self):
        request = self.factory.get('/')
        request.user = self.alice
        device = self.alice.staticdevice_set.get()
        request.session = {DEVICE_ID_SESSION_KEY: device.persistent_id}

        self.middleware(request)

        self.assertTrue(request.user.is_verified())

    def test_verified_legacy_device_id(self):
        request = self.factory.get('/')
        request.user = self.alice
        device = self.alice.staticdevice_set.get()
        request.session = {
            DEVICE_ID_SESSION_KEY: '{}.{}/{}'.format(
                device.__module__, device.__class__.__name__, device.id
            )
        }

        self.middleware(request)

        self.assertTrue(request.user.is_verified())

    def test_unverified(self):
        request = self.factory.get('/')
        request.user = self.alice
        request.session = {}

        self.middleware(request)

        self.assertFalse(request.user.is_verified())

    def test_no_device(self):
        request = self.factory.get('/')
        request.user = self.alice
        request.session = {
            DEVICE_ID_SESSION_KEY: 'otp_static.staticdevice/0',
        }

        self.middleware(request)

        self.assertFalse(request.user.is_verified())

    def test_no_model(self):
        request = self.factory.get('/')
        request.user = self.alice
        request.session = {
            DEVICE_ID_SESSION_KEY: 'otp_bogus.bogusdevice/0',
        }

        self.middleware(request)

        self.assertFalse(request.user.is_verified())

    def test_wrong_user(self):
        request = self.factory.get('/')
        request.user = self.alice
        device = self.bob.staticdevice_set.get()
        request.session = {DEVICE_ID_SESSION_KEY: device.persistent_id}

        self.middleware(request)

        self.assertFalse(request.user.is_verified())

    def test_pickling(self):
        request = self.factory.get('/')
        request.user = self.alice
        device = self.alice.staticdevice_set.get()
        request.session = {DEVICE_ID_SESSION_KEY: device.persistent_id}

        self.middleware(request)

        # Should not raise an exception.
        pickle.dumps(request.user)


class LoginViewTestCase(TestCase):
    def setUp(self):
        try:
            self.alice = self.create_user('alice', 'password')
            self.bob = self.create_user('bob', 'password', is_staff=True)
        except IntegrityError:
            self.skipTest("Unable to create a test user.")
        else:
            for user in [self.alice, self.bob]:
                device = user.staticdevice_set.create()
                device.token_set.create(token=user.get_username())

    def test_admin_login_template(self):
        response = self.client.get(reverse('otpadmin:login'))
        self.assertContains(response, 'Username:')
        self.assertContains(response, 'Password:')
        self.assertNotContains(response, 'OTP Device:')
        self.assertContains(response, 'OTP Token:')
        response = self.client.post(
            reverse('otpadmin:login'),
            data={
                'username': self.bob.get_username(),
                'password': 'password',
            },
        )
        self.assertContains(response, 'Username:')
        self.assertContains(response, 'Password:')
        self.assertContains(response, 'OTP Device:')
        self.assertContains(response, 'OTP Token:')

        device = self.bob.staticdevice_set.get()
        token = device.token_set.get()
        response = self.client.post(
            reverse('otpadmin:login'),
            data={
                'username': self.bob.get_username(),
                'password': 'password',
                'otp_device': device.persistent_id,
                'otp_token': token.token,
                'next': '/',
            },
        )
        self.assertRedirects(response, '/')

    def test_authenticate(self):
        device = self.alice.staticdevice_set.get()
        token = device.token_set.get()

        params = {
            'username': self.alice.get_username(),
            'password': 'password',
            'otp_device': device.persistent_id,
            'otp_token': token.token,
            'next': '/',
        }

        response = self.client.post(reverse('login'), params)
        self.assertRedirects(response, '/')

        response = self.client.get('/')
        self.assertInHTML(
            f'<span id="username">{self.alice.get_username()}</span>',
            response.content.decode(response.charset),
        )

    def test_verify(self):
        device = self.alice.staticdevice_set.get()
        token = device.token_set.get()

        params = {
            'otp_device': device.persistent_id,
            'otp_token': token.token,
            'next': '/',
        }

        self.client.login(username=self.alice.get_username(), password='password')

        response = self.client.post(reverse('login-otp'), params)
        self.assertRedirects(response, '/')

        response = self.client.get('/')
        self.assertInHTML(
            f'<span id="username">{self.alice.get_username()}</span>',
            response.content.decode(response.charset),
        )


@skipUnlessDBFeature('has_select_for_update')
@override_settings(OTP_STATIC_THROTTLE_FACTOR=0)
class ConcurrencyTestCase(TransactionTestCase):
    def setUp(self):
        try:
            self.alice = self.create_user('alice', 'password')
            self.bob = self.create_user('bob', 'password')
        except IntegrityError:
            self.skipTest("Unable to create a test user.")
        else:
            for user in [self.alice, self.bob]:
                device = user.staticdevice_set.create()
                device.token_set.create(token='valid')

    def test_verify_token(self):
        class VerifyThread(Thread):
            def __init__(self, user, device_id, token):
                super().__init__()

                self.user = user
                self.device_id = device_id
                self.token = token

                self.verified = None

            def run(self):
                self.verified = verify_token(self.user, self.device_id, self.token)
                connection.close()

        device = self.alice.staticdevice_set.get()
        threads = [
            VerifyThread(device.user, device.persistent_id, 'valid') for _ in range(10)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sum(1 for t in threads if t.verified is not None), 1)

    def test_match_token(self):
        class VerifyThread(Thread):
            def __init__(self, user, token):
                super().__init__()

                self.user = user
                self.token = token

                self.verified = None

            def run(self):
                self.verified = match_token(self.user, self.token)
                connection.close()

        threads = [VerifyThread(self.alice, 'valid') for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sum(1 for t in threads if t.verified is not None), 1)

    def test_concurrent_throttle_count(self):
        self._test_throttling_concurrency(thread_count=10, expected_failures=10)

    @override_settings(OTP_STATIC_THROTTLE_FACTOR=1)
    def test_serialized_throttling(self):
        # After the first failure, verification will be skipped and the count
        # will not be incremented.
        self._test_throttling_concurrency(thread_count=10, expected_failures=1)

    def _test_throttling_concurrency(self, thread_count, expected_failures):
        forms = (
            OTPTokenForm(
                device.user,
                None,
                {'otp_device': device.persistent_id, 'otp_token': 'bogus'},
            )
            for _ in range(thread_count)
            for device in StaticDevice.objects.all()
        )

        threads = [TestThread(target=form.is_valid) for form in forms]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        for device in StaticDevice.objects.all():
            with self.subTest(user=device.user.get_username()):
                self.assertEqual(device.throttling_failure_count, expected_failures)


class AddStaticTokenTestCase(TestCase):
    def setUp(self):
        try:
            self.alice = self.create_user('alice', 'password')
            self.bob = self.create_user('bob', 'password', is_staff=True)
        except IntegrityError:
            self.skipTest("Unable to create a test user.")

    def test_no_user(self):
        with self.assertRaises(CommandError):
            call_command('addstatictoken', 'bogus')

    def test_new_device(self):
        out = StringIO()
        call_command('addstatictoken', 'alice', stdout=out)
        token = out.getvalue().strip()

        static_token = StaticToken.objects.select_related('device__user').get(
            token=token
        )
        self.assertEqual(static_token.device.user, self.alice)

    def test_existing_device(self):
        device = self.alice.staticdevice_set.create()

        out = StringIO()
        call_command('addstatictoken', 'alice', stdout=out)
        token = out.getvalue().strip()

        static_token = StaticToken.objects.select_related('device__user').get(
            token=token
        )
        self.assertEqual(static_token.device, device)

    def test_explicit_token(self):
        device = self.alice.staticdevice_set.create()

        out = StringIO()
        call_command('addstatictoken', 'alice', '-t', 'secret-token', stdout=out)
        token = out.getvalue().strip()

        static_token = StaticToken.objects.select_related('device__user').get(
            token=token
        )
        self.assertEqual(token, 'secret-token')
        self.assertEqual(static_token.device, device)
