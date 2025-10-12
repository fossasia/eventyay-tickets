"""
Tests for Wikimedia email registration functionality.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from eventyay.person.utils import (
    get_or_create_email_for_wikimedia_user,
    is_wikimedia_user,
    is_placeholder_email,
)

User = get_user_model()


class WikimediaEmailUtilsTests(TestCase):
    """Test utilities for Wikimedia OAuth users."""

    def test_placeholder_email_with_real_email(self):
        """Real email takes precedence over placeholder generation."""
        result = get_or_create_email_for_wikimedia_user('testuser', 'test@example.com')
        self.assertEqual(result, 'test@example.com')

    def test_placeholder_email_without_email(self):
        """Placeholder email generated when no email provided."""
        result = get_or_create_email_for_wikimedia_user('testuser', None, user_id=123)
        self.assertEqual(result, 'testuser.123@wikimedia.local')

    def test_sanitize_username_with_spaces(self):
        """Spaces converted to dots."""
        result = get_or_create_email_for_wikimedia_user('Test User', None, user_id=456)
        self.assertTrue(result.startswith('test.user'))
        self.assertIn('@wikimedia.local', result)

    def test_sanitize_username_with_underscores(self):
        """Underscores converted to dots."""
        result = get_or_create_email_for_wikimedia_user('test_user_name', None, user_id=789)
        self.assertEqual(result, 'test.user.name.789@wikimedia.local')

    def test_remove_special_characters(self):
        """Special characters removed from username."""
        result = get_or_create_email_for_wikimedia_user('test@user#123', None, user_id=101)
        self.assertEqual(result, 'testuser123.101@wikimedia.local')

    def test_empty_username_fallback(self):
        """Empty username uses ID-based fallback."""
        result = get_or_create_email_for_wikimedia_user('', None, user_id=789)
        self.assertEqual(result, 'wm.789@wikimedia.local')

    def test_is_placeholder_email_true(self):
        """Wikimedia.local emails identified as placeholders."""
        self.assertTrue(is_placeholder_email('testuser@wikimedia.local'))

    def test_is_placeholder_email_false(self):
        """Real emails not identified as placeholders."""
        self.assertFalse(is_placeholder_email('test@example.com'))
        self.assertFalse(is_placeholder_email(None))

    def test_is_wikimedia_user_true(self):
        """Wikimedia users correctly identified."""
        user = User.objects.create_user(
            email='test@wikimedia.local',
            is_wikimedia_user=True
        )
        self.assertTrue(is_wikimedia_user(user))

    def test_is_wikimedia_user_false(self):
        """Regular users not identified as Wikimedia users."""
        user = User.objects.create_user(email='test@example.com')
        self.assertFalse(is_wikimedia_user(user))

    def test_wikimedia_user_creation(self):
        """Wikimedia user can be created with placeholder email."""
        email = get_or_create_email_for_wikimedia_user('wikiuser', None, user_id=999)
        user = User.objects.create_user(
            email=email,
            wikimedia_username='wikiuser',
            is_wikimedia_user=True
        )
        self.assertEqual(user.email, 'wikiuser.999@wikimedia.local')
        self.assertTrue(user.is_wikimedia_user)