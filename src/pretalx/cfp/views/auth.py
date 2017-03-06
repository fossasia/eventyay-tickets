from django.contrib.auth import logout
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.views import View

from pretalx.cfp.views.event import EventPageMixin


class LogoutView(EventPageMixin, View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect(reverse('cfp:event.start', kwargs={
            'event': self.request.event.slug
        }))
