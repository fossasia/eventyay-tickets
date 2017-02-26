from django.views.generic import TemplateView


class EventStartpage(TemplateView):
    template_name = 'cfp/event/index.html'
