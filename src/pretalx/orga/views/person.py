from django.db.models import Q
from django.http import JsonResponse
from django.views.generic import View

from pretalx.person.models import User


class UserList(View):

    def dispatch(self, request, *args, **kwargs):
        search = request.GET.get('search')
        if not search or len(search) < 2:
            return JsonResponse({'count': 0, 'results': []})

        queryset = User.objects.filter(
            Q(nick__icontains=search) | Q(name__icontains=search)
        )
        if request.GET.get('orga', 'false') == 'true':
            queryset = queryset.filter(permissions__is_orga=True)

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
