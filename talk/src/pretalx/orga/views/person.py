import urllib

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import View


class SubuserView(View):
    def dispatch(self, request, *args, **kwargs):
        request.user.is_administrator = request.user.is_superuser
        request.user.is_superuser = False
        request.user.save(update_fields=["is_administrator", "is_superuser"])
        messages.success(
            request, _("You are now an administrator instead of a superuser.")
        )
        params = request.GET.copy()
        url = urllib.parse.unquote(params.pop("next", [""])[0])
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            return redirect(url + ("?" + params.urlencode() if params else ""))
        return redirect(reverse("orga:event.list"))
