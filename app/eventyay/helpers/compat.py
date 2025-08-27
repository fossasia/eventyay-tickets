import datetime
import sys

from django.forms import Form
from django.views.generic.detail import (
    BaseDetailView,
    SingleObjectTemplateResponseMixin,
)
from django.views.generic.edit import DeletionMixin, FormMixin


def date_fromisocalendar(isoyear, isoweek, isoday):
    if sys.version_info < (3, 8):
        return datetime.datetime.strptime(f'{isoyear}-W{isoweek}-{isoday}', '%G-W%V-%u')
    else:
        return datetime.datetime.fromisocalendar(isoyear, isoweek, isoday)


class CompatDeleteView(SingleObjectTemplateResponseMixin, DeletionMixin, FormMixin, BaseDetailView):
    """
    This view integrates the ability to show a confirmation template, manage form validation, and delete the object
    when the form is submitted.
    """

    form_class = Form
    template_name_suffix = '_confirm_delete'

    def post(self, request, *args, **kwargs):
        """
        Validate the form and delete the object if it is valid.

        Parameters:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: The response following form validation.
        """
        self.object = self.retrieve_object()
        form = self.retrieve_form()
        return self.process_form(form)

    def retrieve_object(self):
        return self.get_object()

    def retrieve_form(self):
        return self.get_form()

    def process_form(self, form):
        if self.is_form_valid(form):
            return self.handle_valid_form(form)
        else:
            return self.handle_invalid_form(form)

    def is_form_valid(self, form):
        return form.is_valid()

    def handle_valid_form(self, form):
        return self.form_valid(form)

    def handle_invalid_form(self, form):
        return self.form_invalid(form)

    def form_valid(self, form):
        """
        Remove the object and redirect to the success URL.
        """
        return self.perform_deletion()

    def perform_deletion(self):
        return self.delete(self.request, self.args, self.kwargs)
