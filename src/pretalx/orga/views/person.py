import urllib

from django.contrib import messages
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import is_safe_url
from django.utils.translation import ugettext as _
from django.views.generic import View

from pretalx.person.models import EventPermission, User


class UserList(View):

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('orga.search_all_users', request.event):
            raise Http404()

        search = request.GET.get('search')
        if not search or len(search) < 2:
            return JsonResponse({'count': 0, 'results': []})

        queryset = User.objects.filter(
            Q(nick__icontains=search) | Q(name__icontains=search)
        )
        if request.GET.get('orga', 'false').lower() == 'true':
            permissions = EventPermission.objects.filter(event=self.request.event, is_orga=True)
            queryset = queryset.filter(permissions__in=permissions)

        return JsonResponse({
            'count': len(queryset),
            'results': [
                {
                    'nick': user.nick,
                    'name': user.name,
                }
                for user in queryset
            ],
        })


class SubuserView(View):

    def dispatch(self, request, *args, **kwargs):
        request.user.is_administrator = request.user.is_superuser
        request.user.is_superuser = False
        request.user.save(update_fields=['is_administrator', 'is_superuser'])
        messages.success(request, _('You are now an administrator instead of a superuser.'))
        params = request.GET.copy()
        url = urllib.parse.unquote(params.pop('next', [''])[0])
        if url and is_safe_url(url, request.get_host()):
            return redirect(url + ('?' + params.urlencode() if params else ''))
        return redirect(reverse('orga:dashboard'))
