from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from zxcvbn import zxcvbn


class ZXCVBNValidator:
    code = 'password_too_weak'
    DEFAULT_USER_ATTRIBUTES = ('username', 'first_name', 'last_name', 'email')

    def __init__(self, min_score=3, user_attributes=DEFAULT_USER_ATTRIBUTES):
        if not (0 <= min_score <= 4):
            raise Exception('min_score must be between 0 and 4!')
        self.min_score = min_score
        self.user_attributes = user_attributes

    def __call__(self, value):
        return self.validate(value)

    def validate(self, password, user=None):
        user_inputs = [getattr(user, attribute, None) for attribute in self.user_attributes]
        user_inputs = [attr for attr in user_inputs if attr is not None]
        results = zxcvbn(password, user_inputs=user_inputs)
        if results.get('score', 0) < self.min_score:
            feedback = ', '.join(results.get('feedback', {}).get('suggestions', []))
            raise ValidationError(_(feedback), code=self.code, params={})

    def get_help_text(self):
        return _('Your password is too weak.')
