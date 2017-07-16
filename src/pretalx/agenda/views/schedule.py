from django.views.generic import TemplateView, View


class ScheduleView(TemplateView):
    template_name = 'agenda/schedule.html'

    def get_object(self):
        if self.request.GET.get('version'):
            return self.request.event.schedules.filter(version=self.request.GET.get('version'))
        return self.request.event.current_schedule

    def get_context_data(self):
        ctx = super().get_context_data()
        schedule = self.get_object()

        if not schedule and self.request.GET.get('version'):
            ctx['version'] = self.request.GET.get('version')
            ctx['error'] = 'wrong-version'
            return ctx
        elif not schedule:
            ctx['error'] = 'no-schedule'
            return ctx
        ctx['schedule'] = schedule
        ctx['schedules'] = self.request.event.schedules.filter(published__isnull=False).values_list('version')
        return ctx


class TalkView(View):
    pass
