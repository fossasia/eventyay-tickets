from django.contrib.auth.tokens import PasswordResetTokenGenerator

class TokenGenerator(PasswordResetTokenGenerator):
    key_salt = "$2a$12$xoUY1cRjQ0gWdF/LI8rmV.Ex5pWuhF5d.sgUJsAV0Ki7CUXZCPn8y"
