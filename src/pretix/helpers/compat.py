import datetime
import sys
from django.forms import Form
from django.views.generic.detail import (
    BaseDetailView, SingleObjectTemplateResponseMixin,
)
from django.views.generic.edit import DeletionMixin, FormMixin


def date_fromisocalendar(isoyear, isoweek, isoday):
    if sys.version_info < (3, 8):
        return datetime.datetime.strptime(f'{isoyear}-W{isoweek}-{isoday}', "%G-W%V-%u")
    else:
        return datetime.datetime.fromisocalendar(isoyear, isoweek, isoday)


class CompatDeleteView(SingleObjectTemplateResponseMixin, DeletionMixin, FormMixin, BaseDetailView):
    """
    This view combines the functionality of displaying a confirmation template,
    handling form validation, and deleting the object upon form submission.
    """
    form_class = Form
    template_name_suffix = "_confirm_delete"

    def post(self, request, *args, **kwargs):
        """
        Validate the form and delete the object if the form is valid.

        Parameters:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: The response after form validation.
        """
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """
        Delete the object and redirect to the success URL.
        """
        return self.delete(self.request, self.args, self.kwargs)
