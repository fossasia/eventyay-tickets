from django.forms import PasswordInput
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _


class PasswordStrengthInput(PasswordInput):

    def render(self, name, value, attrs=None):
        markup = """
        <div class="password-progress">
            <div class="password-progress-bar progress">
                <div class="progress-bar progress-bar-warning password_strength_bar"
                     role="progressbar"
                     aria-valuenow="0"
                     aria-valuemin="0"
                     aria-valuemax="4">
                </div>
            </div>
            <p class="text-muted password_strength_info hidden">
                <span style="margin-left:5px;">
                    {message}
                </span>
            </p>
        </div>
        """.format(message=_('This password would take <em class="password_strength_time"></em> to crack.'))

        self.attrs['class'] = ' '.join(self.attrs.get('class', '').split(' ') + ['password_strength'])
        return mark_safe(super().render(name, value, self.attrs) + markup)

    class Media(object):
        js = ('common/js/zxcvbn.js', 'common/js/password_strength.js')


class PasswordConfirmationInput(PasswordInput):

    def __init__(self, confirm_with=None, attrs=None, render_value=False):
        super().__init__(attrs, render_value)
        self.confirm_with = confirm_with

    def render(self, name, value, attrs=None):
        if self.confirm_with:
            self.attrs['data-confirm-with'] = f'{self.confirm_with}'

        markup = """
        <div class="hidden password_strength_info">
            <p class="text-muted">
                <span class="label label-danger">{warning}</span>
                <span>{content}</span>
            </p>
        </div>
        """.format(warning=_('Warning'), content=_("Your passwords don't match."))

        self.attrs['class'] = ' '.join(self.attrs.get('class', '').split(' ') + ['password_confirmation'])

        return mark_safe(super(PasswordInput, self).render(name, value, self.attrs) + markup)
