from django.views.generic import TemplateView


class ScheduleView(TemplateView):
    template_name = 'orga/schedule/index.html'
