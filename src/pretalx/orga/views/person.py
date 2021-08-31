import urllib

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.generic import View
from django_scopes import scopes_disabled

from pretalx.event.models import Organiser, Team
from pretalx.person.models import SpeakerProfile, User


class UserList(View):
    def dispatch(self, request, *args, **kwargs):
        search = request.GET.get("search")
        if not search or len(search) < 3:
            return JsonResponse({"count": 0, "results": []})

        if request.GET.get("orga", "false").lower() == "true":
            if request.user.is_administrator:
                organisers = Organiser.objects.all()
            else:
                user_teams = request.user.teams.filter(
                    can_change_organiser_settings=True
                )
                organisers = Organiser.objects.filter(teams__in=user_teams)
            teams = Team.objects.filter(organiser__in=organisers)
            users = User.objects.filter(
                Q(name__icontains=search) | Q(email__icontains=search),
                teams__in=teams,
            )[:8]
        else:
            events = self.request.user.get_events_for_permission(
                can_change_submissions=True
            )
            with scopes_disabled():
                users = list(
                    set(
                        SpeakerProfile.objects.filter(
                            Q(user__name__icontains=search)
                            | Q(user__email__icontains=search),
                            event__in=events,
                        ).values_list("user", flat=True)
                    )
                )
            users = User.objects.filter(pk__in=users[:8])

        return JsonResponse(
            {
                "count": len(users),
                "results": [{"email": user.email, "name": user.name} for user in users],
            }
        )


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
