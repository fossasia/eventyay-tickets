from django.db.models import Q
from django.http import JsonResponse
from django.views.generic import View

from pretalx.person.models import User


class UserList(View):

    def dispatch(self, request, *args, **kwargs):
        search = request.GET.get('search')
        if not search or len(search) < 3:
            return JsonResponse([], safe=False)

        queryset = User.objects.filter(
            Q(nick__icontains=search) | Q(name__icontains=search)
        )
        return JsonResponse([
            {
                'nick': user.nick,
                'name': user.name,
            }
            for user in queryset
        ], safe=False)
