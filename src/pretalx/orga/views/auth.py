from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.urlresolvers import reverse
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
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
        url = request.GET.get('next')
        if url and is_safe_url(url, request.get_host()):
            return redirect(url)

        # check where to reasonably redirect:
        # orga of a running event? go to that event.
        # speaker of a running event? go to that event.
        # neither? go to (a) current cfp
        # no current cfp? dummy page

        messages.success(request, _('Hi!'))
        return redirect('orga:dashboard')


def logout_view(request: HttpRequest) -> HttpResponseRedirect:
    logout(request)
    return redirect('orga:login')
