from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView, UpdateView

from pretix.base.channels import get_all_sales_channels
from pretix.base.models.customers import Customer
from pretix.base.models.invoices import Invoice
from pretix.base.models.orders import CancellationRequest, Order, OrderPosition
from pretix.control.forms.filter import CustomerFilterForm
from pretix.control.forms.organizer_forms import CustomerUpdateForm
from pretix.control.permissions import OrganizerPermissionRequiredMixin
from pretix.control.views import PaginationMixin
from pretix.control.views.organizer_views.organizer_detail_view_mixin import (
    OrganizerDetailViewMixin,
)


class CustomerListView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, PaginationMixin, ListView):
    model = Customer
    template_name = 'pretixcontrol/organizers/customers.html'
    permission = 'can_manage_customers'
    context_object_name = 'customers'

    def get_queryset(self):
        """
        Returns the filtered queryset of customers based on the organizer's settings and the validity of the filter form.

        Returns:
            QuerySet: The filtered queryset of customers.
        """
        qs = self.request.organizer.customers.all()

        if self.filter_form.is_valid():
            qs = self.filter_form.filter_qs(qs)

        return qs

    def get_context_data(self, **kwargs):
        """
        Returns the context data for the view, including the filter form.

        Args:
            **kwargs: Arbitrary keyword arguments.

        Returns:
            dict: The context data including the filter form.
        """
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filter_form
        return ctx

    @cached_property
    def filter_form(self):
        return CustomerFilterForm(data=self.request.GET, request=self.request)


class CustomerDetailView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, PaginationMixin, ListView):
    template_name = 'pretixcontrol/organizers/customer.html'
    permission = 'can_manage_customers'
    context_object_name = 'orders'

    def get_queryset(self):
        """
        Returns the queryset of orders for the specified customer, including orders that match the customer's email,
        and orders are sorted by datetime in descending order.

        Returns:
            QuerySet: The queryset of orders.
        """
        return Order.objects.filter(
            Q(customer=self.customer) | Q(email__iexact=self.customer.email)
        ).select_related('event').order_by('-datetime')

    @cached_property
    def customer(self):
        return get_object_or_404(
            self.request.organizer.customers,
            identifier=self.kwargs.get('customer')
        )

    def get_context_data(self, **kwargs):
        """
        Returns the context data for the view, including customer details, locale, and annotated order information.

        Args:
            **kwargs: Arbitrary keyword arguments.

        Returns:
            dict: The context data including customer details and annotated orders.
        """
        ctx = super().get_context_data(**kwargs)
        ctx['customer'] = self.customer
        ctx['display_locale'] = dict(settings.LANGUAGES).get(self.customer.locale,
                                                             self.request.organizer.settings.locale)

        s = OrderPosition.objects.filter(
            order=OuterRef('pk')
        ).order_by().values('order').annotate(k=Count('id')).values('k')
        i = Invoice.objects.filter(
            order=OuterRef('pk'),
            is_cancellation=False,
            refered__isnull=True,
        ).order_by().values('order').annotate(k=Count('id')).values('k')
        orders = ctx.get('orders', [])
        order_pks = [o.pk for o in orders]

        annotated_orders = Order.annotate_overpayments(Order.objects, sums=True).filter(
            pk__in=order_pks
        ).annotate(
            pcnt=Subquery(s, output_field=IntegerField()),
            icnt=Subquery(i, output_field=IntegerField()),
            has_cancellation_request=Exists(CancellationRequest.objects.filter(order=OuterRef('pk')))
        ).values(
            'pk', 'pcnt', 'is_overpaid', 'is_underpaid', 'is_pending_with_full_payment', 'has_external_refund',
            'has_pending_refund', 'has_cancellation_request', 'computed_payment_refund_sum', 'icnt'
        )

        annotated = {o['pk']: o for o in annotated_orders}

        scs = get_all_sales_channels()

        for order in orders:
            if order.pk not in annotated:
                continue
            annotation = annotated[order.pk]
            order.pcnt = annotation['pcnt']
            order.is_overpaid = annotation['is_overpaid']
            order.is_underpaid = annotation['is_underpaid']
            order.is_pending_with_full_payment = annotation['is_pending_with_full_payment']
            order.has_external_refund = annotation['has_external_refund']
            order.has_pending_refund = annotation['has_pending_refund']
            order.has_cancellation_request = annotation['has_cancellation_request']
            order.computed_payment_refund_sum = annotation['computed_payment_refund_sum']
            order.icnt = annotation['icnt']
            order.sales_channel_obj = scs[order.sales_channel]

        return ctx


class CustomerUpdateView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, UpdateView):
    template_name = 'pretixcontrol/organizers/customer_edit.html'
    permission = 'can_manage_customers'
    context_object_name = 'customer'
    form_class = CustomerUpdateForm

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.request.organizer.customers,
            identifier=self.kwargs.get('customer')
        )

    def form_valid(self, form):
        """
        Handles the form validation and logging of changes. If the form has changed, logs the action with the changed data.

        Args:
            form (Form): The validated form.

        Returns:
            HttpResponse: The response generated by the superclass method.
        """
        if form.has_changed():
            self.object.log_action(
                'pretix.customer.changed',
                user=self.request.user,
                data={k: getattr(self.object, k) for k in form.changed_data}
            )
            messages.success(self.request, _('Your changes have been saved.'))

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('control:organizer.customer', kwargs={
            'organizer': self.request.organizer.slug,
            'customer': self.object.identifier,
        })


class CustomerAnonymizeView(OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, DetailView):
    template_name = 'pretixcontrol/organizers/customer_anonymize.html'
    permission = 'can_manage_customers'
    context_object_name = 'customer'

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.request.organizer.customers,
            identifier=self.kwargs.get('customer')
        )

    def post(self, request, *args, **kwargs):
        """
        Handles the POST request to anonymize a customer account. Anonymizes the customer,
        logs the action, and redirects to the success URL.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponseRedirect: Redirects to the success URL.
        """
        self.object = self.get_object()

        with transaction.atomic():
            self.object.anonymize_customer()
            self.object.log_action('pretix.customer.anonymized', user=self.request.user)

        messages.success(self.request, _('The customer account has been anonymized.'))

        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('control:organizer.customer', kwargs={
            'organizer': self.request.organizer.slug,
            'customer': self.object.identifier,
        })
