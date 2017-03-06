from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.views.generic import (
    CreateView, DetailView, ListView, TemplateView, UpdateView, View,
)

from pretalx.orga.authorization import OrgaPermissionRequired
from pretalx.person.models import User


class SpeakerList(OrgaPermissionRequired, ListView):
    template_name = 'orga/speaker/list.html'
    context_object_name = 'speakers'

    def get_queryset(self):
        return User.objects.filter(submissions__in=self.request.event.submissions.all())
