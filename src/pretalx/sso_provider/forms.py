from allauth.socialaccount.forms import SignupForm

class CustomSignUpForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO add custom fields here
