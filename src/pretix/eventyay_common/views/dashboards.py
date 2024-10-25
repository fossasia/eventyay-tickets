from django.conf import settings
from django.shortcuts import render


def organiser_dashboard(request):
    context = {
        'ticket_component': settings.SITE_URL + '/control',
        'talk_component': settings.TALK_HOSTNAME + '/orga',
        'video_component': '#',
    }
    return render(request, 'eventyay_common/dashboard/dashboard.html', context)
