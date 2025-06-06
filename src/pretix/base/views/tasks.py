import logging

import celery.exceptions
from celery.result import AsyncResult
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.test import RequestFactory
from django.utils.translation import gettext as _
from django.views.generic import FormView

from pretix.base.models import User
from pretix.base.services.tasks import ProfiledEventTask
from pretix.celery_app import app

logger = logging.getLogger('pretix.base.tasks')


class AsyncMixin:
    success_url = None
    error_url = None
    known_errortypes = []

    def get_success_url(self, value):
        return self.success_url

    def get_error_url(self):
        return self.error_url

    def get_check_url(self, task_id, ajax):
        return self.request.path + '?async_id=%s' % task_id + ('&ajax=1' if ajax else '')

    def _ajax_response_data(self):
        return {}

    def _return_ajax_result(self, res, timeout=0.5):
        if not res.ready():
            try:
                res.get(timeout=timeout, propagate=False)
            except celery.exceptions.TimeoutError:
                pass
            except ConnectionError:
                # Redis probably just restarted, let's just report not ready and retry next time
                data = self._ajax_response_data()
                data.update({'async_id': res.id, 'ready': False})
                return data

        ready = res.ready()
        data = self._ajax_response_data()
        data.update(
            {
                'async_id': res.id,
                'ready': ready,
                'started': False,
            }
        )
        if ready:
            if res.successful() and not isinstance(res.info, Exception):
                smes = self.get_success_message(res.info)
                if smes:
                    messages.success(self.request, smes)
                # TODO: Do not store message if the ajax client states that it will not redirect
                # but handle the message itself
                data.update(
                    {
                        'redirect': self.get_success_url(res.info),
                        'success': True,
                        'message': str(self.get_success_message(res.info)),
                    }
                )
            else:
                messages.error(self.request, self.get_error_message(res.info))
                # TODO: Do not store message if the ajax client states that it will not redirect
                # but handle the message itself
                data.update(
                    {
                        'redirect': self.get_error_url(),
                        'success': False,
                        'message': str(self.get_error_message(res.info)),
                    }
                )
        elif res.state == 'PROGRESS':
            data.update({'started': True, 'percentage': res.result.get('value', 0)})
        elif res.state == 'STARTED':
            data.update(
                {
                    'started': True,
                }
            )
        return data

    def get_result(self, request):
        res = AsyncResult(request.GET.get('async_id'))
        if 'ajax' in self.request.GET:
            return JsonResponse(self._return_ajax_result(res, timeout=0.25))
        else:
            if res.ready():
                if res.successful() and not isinstance(res.info, Exception):
                    return self.success(res.info)
                else:
                    return self.error(res.info)
            return render(request, 'pretixpresale/waiting.html')

    def success(self, value):
        smes = self.get_success_message(value)
        if smes:
            messages.success(self.request, smes)
        if 'ajax' in self.request.POST or 'ajax' in self.request.GET:
            return JsonResponse(
                {
                    'ready': True,
                    'success': True,
                    'redirect': self.get_success_url(value),
                    'message': str(self.get_success_message(value)),
                }
            )
        return redirect(self.get_success_url(value))

    def error(self, exception):
        messages.error(self.request, self.get_error_message(exception))
        if 'ajax' in self.request.POST or 'ajax' in self.request.GET:
            return JsonResponse(
                {
                    'ready': True,
                    'success': False,
                    'redirect': self.get_error_url(),
                    'message': str(self.get_error_message(exception)),
                }
            )
        return redirect(self.get_error_url())

    def get_error_message(self, exception):
        if isinstance(exception, dict) and exception['exc_type'] in self.known_errortypes:
            return exception['exc_message']
        elif exception.__class__.__name__ in self.known_errortypes:
            return str(exception)
        else:
            logger.error('Unexpected exception: %r' % exception)
            return _('An unexpected error has occurred, please try again later.')

    def get_success_message(self, value):
        return _('The task has been completed.')


class AsyncAction(AsyncMixin):
    task = None

    def do(self, *args, **kwargs):
        if not isinstance(self.task, app.Task):
            raise TypeError('Method has no task attached')

        try:
            res = self.task.apply_async(args=args, kwargs=kwargs)
        except ConnectionError:
            # Task very likely not yet sent, due to redis restarting etc. Let's try once again
            res = self.task.apply_async(args=args, kwargs=kwargs)

        if 'ajax' in self.request.GET or 'ajax' in self.request.POST:
            data = self._return_ajax_result(res)
            data['check_url'] = self.get_check_url(res.id, True)
            return JsonResponse(data)
        else:
            if res.ready():
                if res.successful() and not isinstance(res.info, Exception):
                    return self.success(res.info)
                else:
                    return self.error(res.info)
            return redirect(self.get_check_url(res.id, False))

    def get(self, request, *args, **kwargs):
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return self.get_result(request)
        return self.http_method_not_allowed(request)


class AsyncFormView(AsyncMixin, FormView):
    """
    FormView variant in which instead of ``form_valid``, an ``async_form_valid``
    is executed in a celery task. Note that this places some severe limitations
    on the form and the view, e.g. neither ``get_form*`` nor the form itself
    may depend on the request object unless specifically supported by this class.
    Also, all form keyword arguments except ``instance`` need to be serializable.
    """

    known_errortypes = ['ValidationError']

    def __init_subclass__(cls):
        def async_execute(self, request_path, form_kwargs, organizer=None, event=None, user=None):
            view_instance = cls()
            view_instance.request = RequestFactory().post(request_path)
            if organizer:
                view_instance.request.event = event
            if organizer:
                view_instance.request.organizer = organizer
            if user:
                view_instance.request.user = User.objects.get(pk=user)

            form_class = view_instance.get_form_class()
            if form_kwargs.get('instance'):
                cls.model.objects.get(pk=form_kwargs['instance'])

            form_kwargs = view_instance.get_async_form_kwargs(form_kwargs, organizer, event)

            form = form_class(**form_kwargs)
            return view_instance.async_form_valid(self, form)

        cls.async_execute = app.task(
            base=ProfiledEventTask,
            bind=True,
            name=cls.__module__ + '.' + cls.__name__ + '.async_execute',
            throws=(ValidationError,),
        )(async_execute)

    def async_form_valid(self, task, form):
        pass

    def get_async_form_kwargs(self, form_kwargs, organizer=None, event=None):
        return form_kwargs

    def get(self, request, *args, **kwargs):
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return self.get_result(request)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        if form.files:
            raise TypeError('File upload currently not supported in AsyncFormView')
        form_kwargs = {k: v for k, v in self.get_form_kwargs().items()}
        if form_kwargs.get('instance'):
            if form_kwargs['instance'].pk:
                form_kwargs['instance'] = form_kwargs['instance'].pk
            else:
                form_kwargs['instance'] = None
        form_kwargs.setdefault('data', {})
        kwargs = {
            'request_path': self.request.path,
            'form_kwargs': form_kwargs,
        }
        if hasattr(self.request, 'organizer'):
            kwargs['organizer'] = self.request.organizer.pk
        if self.request.user.is_authenticated:
            kwargs['user'] = self.request.user.pk
        if hasattr(self.request, 'event'):
            kwargs['event'] = self.request.event.pk

        try:
            res = type(self).async_execute.apply_async(kwargs=kwargs)
        except ConnectionError:
            # Task very likely not yet sent, due to redis restarting etc. Let's try once again
            res = type(self).async_execute.apply_async(kwargs=kwargs)

        if 'ajax' in self.request.GET or 'ajax' in self.request.POST:
            data = self._return_ajax_result(res)
            data['check_url'] = self.get_check_url(res.id, True)
            return JsonResponse(data)
        else:
            if res.ready():
                if res.successful() and not isinstance(res.info, Exception):
                    return self.success(res.info)
                else:
                    return self.error(res.info)
            return redirect(self.get_check_url(res.id, False))
