import random
import urllib

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import is_safe_url
from django.utils.translation import ugettext as _
from django.views.generic import TemplateView


class LoginView(TemplateView):
    template_name = 'orga/auth/login.html'

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponseRedirect:
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)

        if user is None:
            messages.error(request, _('No user account matches the entered credentials.'))
            return redirect('orga:login')

        if not user.is_active:
            messages.error(request, _('User account is deactivated.'))
            return redirect('orga:login')

        login(request, user)
        params = request.GET.copy()
        url = urllib.parse.unquote(params.pop('next', [''])[0])
        if url and is_safe_url(url, request.get_host()):
            return redirect(url + ('?' + params.urlencode() if params else ''))

        # check where to reasonably redirect:
        # orga of a running event? go to that event.
        # speaker of a running event? go to that event.
        # neither? go to (a) current cfp
        # no current cfp? dummy page

        messages.success(request, random.choice([
            _('Hi, nice to see you!'),
            _('Welcome!'),
            _('I hope you are having a good day :)'),
            _('Remember: organizing events is lots of work, but it pays off.'),
            _('If you are waiting for feedback from your speakers, try sending a mail to a subset of them.'),
            _('Remember to provide your speakers with all information they need ahead of time.'),
            _('Even the busiest event organizers should make time to see at least one talk ;)'),
        ]))
        return redirect(reverse('orga:dashboard'))


def logout_view(request: HttpRequest) -> HttpResponseRedirect:
    logout(request)
    return redirect(reverse('orga:login'))
