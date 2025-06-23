from django.test import utils
from django_scopes import scopes_disabled

utils.setup_databases = scopes_disabled()(utils.setup_databases)
