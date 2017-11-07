from django.http import Http404
from rules.contrib.views import PermissionRequiredMixin


class PermissionRequired(PermissionRequiredMixin):

    def get_login_url(self):
        """ We do this to avoid leaking data about existing pages. """
        raise Http404()
