from django.views.generic import TemplateView


class ServiceWorker(TemplateView):
    template_name = 'agenda/sw.js'
    content_type = 'application/javascript'
