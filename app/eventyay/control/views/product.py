import json
from collections import OrderedDict, namedtuple
from json.decoder import JSONDecodeError

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q
from django.forms.models import inlineformset_factory
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import DeleteView
from django_countries.fields import Country

from eventyay.api.serializers.product import (
    ProductAddOnSerializer,
    ProductBundleSerializer,
    ProductVariationSerializer,
)
from eventyay.base.forms import I18nFormSet
from eventyay.base.models import (
    CartPosition,
    Product,
    ProductCategory,
    ProductVariation,
    Order,
    Question,
    QuestionAnswer,
    QuestionOption,
    Quota,
    Voucher,
)
from eventyay.base.models.event import SubEvent
from eventyay.base.models.product import ProductAddOn, ProductBundle, ProductMetaValue
from eventyay.base.services.quotas import QuotaAvailability
from eventyay.base.services.tickets import invalidate_cache
from eventyay.base.signals import quota_availability
from eventyay.control.forms.product import (
    CategoryForm,
    DescriptionForm,
    ProductAddOnForm,
    ProductAddOnsFormSet,
    ProductBundleForm,
    ProductBundleFormSet,
    ProductCreateForm,
    ProductMetaValueForm,
    ProductUpdateForm,
    ProductVariationForm,
    ProductVariationsFormSet,
    QuestionForm,
    QuestionOptionForm,
    QuotaForm,
)
from eventyay.control.permissions import (
    EventPermissionRequiredMixin,
    event_permission_required,
)
from eventyay.control.signals import product_forms, product_formsets
from eventyay.helpers.models import modelcopy

from ...base.channels import get_all_sales_channels
from . import ChartContainingView, CreateView, PaginationMixin, UpdateView


class ProductList(ListView):
    model = Product
    context_object_name = 'products'
    # paginate_by = 30
    # Pagination is disabled as it is very unlikely to be necessary
    # here and could cause problems with the "reorder-within-category" feature
    template_name = 'pretixcontrol/items/index.html'

    def get_queryset(self):
        return (
            Product.objects.filter(event=self.request.event)
            .annotate(var_count=Count('variations'))
            .prefetch_related('category')
            .order_by('category__position', 'category', 'position')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['sales_channels'] = get_all_sales_channels()
        return ctx


def product_move(request, product, up=True):
    """
    This is a helper function to avoid duplicating code in product_move_up and
    product_move_down. It takes an product and a direction and then tries to bring
    all products for this category in a new order.
    """
    try:
        product = request.event.products.get(id=product)
    except Product.DoesNotExist:
        raise Http404(_('The requested product does not exist.'))
    products = list(request.event.products.filter(category=product.category).order_by('position'))

    index = products.index(product)
    if index != 0 and up:
        products[index - 1], products[index] = products[index], products[index - 1]
    elif index != len(products) - 1 and not up:
        products[index + 1], products[index] = products[index], products[index + 1]

    for i, product in enumerate(products):
        if product.position != i:
            product.position = i
            product.save()
    messages.success(request, _('The order of products has been updated.'))


@event_permission_required('can_change_items')
def product_move_up(request, organizer, event, product):
    product_move(request, product, up=True)
    return redirect(
        'control:event.products',
        organizer=request.event.organizer.slug,
        event=request.event.slug,
    )


@event_permission_required('can_change_items')
def product_move_down(request, organizer, event, product):
    product_move(request, product, up=False)
    return redirect(
        'control:event.products',
        organizer=request.event.organizer.slug,
        event=request.event.slug,
    )


class CategoryDelete(EventPermissionRequiredMixin, DeleteView):
    model = ProductCategory
    template_name = 'pretixcontrol/items/category_delete.html'
    permission = 'can_change_items'
    context_object_name = 'category'

    def get_object(self, queryset=None) -> ProductCategory:
        try:
            return self.request.event.categories.get(id=self.kwargs['category'])
        except ProductCategory.DoesNotExist:
            raise Http404(_('The requested product category does not exist.'))

    @transaction.atomic
    def form_valid(self, form):
        self.object = self.get_object()
        for product in self.object.products.all():
            product.category = None
            product.save()
        success_url = self.get_success_url()
        self.object.log_action('pretix.event.category.deleted', user=self.request.user)
        self.object.delete()
        messages.success(self.request, _('The selected category has been deleted.'))
        return HttpResponseRedirect(success_url)

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products.categories',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


class CategoryUpdate(EventPermissionRequiredMixin, UpdateView):
    model = ProductCategory
    form_class = CategoryForm
    template_name = 'pretixcontrol/items/category.html'
    permission = 'can_change_items'
    context_object_name = 'category'

    def get_object(self, queryset=None) -> ProductCategory:
        url = resolve(self.request.path_info)
        try:
            return self.request.event.categories.get(id=url.kwargs['category'])
        except ProductCategory.DoesNotExist:
            raise Http404(_('The requested product category does not exist.'))

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))
        if form.has_changed():
            self.object.log_action(
                'pretix.event.category.changed',
                user=self.request.user,
                data={k: form.cleaned_data.get(k) for k in form.changed_data},
            )
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products.categories',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class CategoryCreate(EventPermissionRequiredMixin, CreateView):
    model = ProductCategory
    form_class = CategoryForm
    template_name = 'pretixcontrol/items/category.html'
    permission = 'can_change_items'
    context_object_name = 'category'

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products.categories',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    @cached_property
    def copy_from(self):
        if self.request.GET.get('copy_from') and not getattr(self, 'object', None):
            try:
                return self.request.event.categories.get(pk=self.request.GET.get('copy_from'))
            except ProductCategory.DoesNotExist:
                pass

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        if self.copy_from:
            i = modelcopy(self.copy_from)
            i.pk = None
            kwargs['instance'] = i
        else:
            kwargs['instance'] = ProductCategory(event=self.request.event)
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        form.instance.event = self.request.event
        messages.success(self.request, _('The new category has been created.'))
        ret = super().form_valid(form)
        form.instance.log_action(
            'pretix.event.category.added',
            data=dict(form.cleaned_data),
            user=self.request.user,
        )
        return ret

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class CategoryList(PaginationMixin, ListView):
    model = ProductCategory
    context_object_name = 'categories'
    template_name = 'pretixcontrol/items/categories.html'

    def get_queryset(self):
        return self.request.event.categories.all()


def category_move(request, category, up=True):
    """
    This is a helper function to avoid duplicating code in category_move_up and
    category_move_down. It takes a category and a direction and then tries to bring
    all categories for this event in a new order.
    """
    try:
        category = request.event.categories.get(id=category)
    except ProductCategory.DoesNotExist:
        raise Http404(_('The requested product category does not exist.'))
    categories = list(request.event.categories.order_by('position'))

    index = categories.index(category)
    if index != 0 and up:
        categories[index - 1], categories[index] = (
            categories[index],
            categories[index - 1],
        )
    elif index != len(categories) - 1 and not up:
        categories[index + 1], categories[index] = (
            categories[index],
            categories[index + 1],
        )

    for i, cat in enumerate(categories):
        if cat.position != i:
            cat.position = i
            cat.save()
    messages.success(request, _('The order of categories has been updated.'))


@event_permission_required('can_change_items')
def category_move_up(request, organizer, event, category):
    category_move(request, category, up=True)
    return redirect(
        'control:event.products.categories',
        organizer=request.event.organizer.slug,
        event=request.event.slug,
    )


@event_permission_required('can_change_items')
def category_move_down(request, organizer, event, category):
    category_move(request, category, up=False)
    return redirect(
        'control:event.products.categories',
        organizer=request.event.organizer.slug,
        event=request.event.slug,
    )


FakeQuestion = namedtuple('FakeQuestion', 'id question position required')


class QuestionList(ListView):
    model = Question
    context_object_name = 'questions'
    template_name = 'pretixcontrol/items/questions.html'

    def get_queryset(self):
        return self.request.event.questions.prefetch_related('products')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['questions'] = list(ctx['questions'])

        if self.request.event.settings.attendee_names_asked:
            ctx['questions'].append(
                FakeQuestion(
                    id='attendee_name_parts',
                    question=_('Attendee name'),
                    position=self.request.event.settings.system_question_order.get('attendee_name_parts', 0),
                    required=self.request.event.settings.attendee_names_required,
                )
            )

        if self.request.event.settings.attendee_emails_asked:
            ctx['questions'].append(
                FakeQuestion(
                    id='attendee_email',
                    question=_('Attendee email'),
                    position=self.request.event.settings.system_question_order.get('attendee_email', 0),
                    required=self.request.event.settings.attendee_emails_required,
                )
            )

        if self.request.event.settings.attendee_emails_asked:
            ctx['questions'].append(
                FakeQuestion(
                    id='company',
                    question=_('Company'),
                    position=self.request.event.settings.system_question_order.get('company', 0),
                    required=self.request.event.settings.attendee_company_required,
                )
            )

        if self.request.event.settings.attendee_addresses_asked:
            ctx['questions'].append(
                FakeQuestion(
                    id='street',
                    question=_('Street'),
                    position=self.request.event.settings.system_question_order.get('street', 0),
                    required=self.request.event.settings.attendee_addresses_required,
                )
            )
            ctx['questions'].append(
                FakeQuestion(
                    id='zipcode',
                    question=_('ZIP code'),
                    position=self.request.event.settings.system_question_order.get('zipcode', 0),
                    required=self.request.event.settings.attendee_addresses_required,
                )
            )
            ctx['questions'].append(
                FakeQuestion(
                    id='city',
                    question=_('City'),
                    position=self.request.event.settings.system_question_order.get('city', 0),
                    required=self.request.event.settings.attendee_addresses_required,
                )
            )
            ctx['questions'].append(
                FakeQuestion(
                    id='country',
                    question=_('Country'),
                    position=self.request.event.settings.system_question_order.get('country', 0),
                    required=self.request.event.settings.attendee_addresses_required,
                )
            )

        ctx['questions'].sort(key=lambda q: q.position)
        return ctx


@transaction.atomic
@event_permission_required('can_change_items')
def reorder_questions(request, organizer, event):
    try:
        ids = json.loads(request.body.decode('utf-8'))['ids']
    except (JSONDecodeError, KeyError, ValueError):
        return HttpResponseBadRequest('expected JSON: {ids:[]}')

    input_questions = request.event.questions.filter(id__in=[i for i in ids if i.isdigit()])

    if input_questions.count() != len([i for i in ids if i.isdigit()]):
        raise Http404(_('Some of the provided question ids are invalid.'))

    if input_questions.count() != request.event.questions.count():
        raise Http404(_('Not all questions have been selected.'))

    for q in input_questions:
        pos = ids.index(str(q.pk))
        if pos != q.position:  # Save unneccessary UPDATE queries
            q.position = pos
            q.save(update_fields=['position'])

    system_question_order = {}
    for s in (
        'attendee_name_parts',
        'attendee_email',
        'company',
        'street',
        'zipcode',
        'city',
        'country',
    ):
        if s in ids:
            system_question_order[s] = ids.index(s)
        else:
            system_question_order[s] = -1
    request.event.settings.system_question_order = system_question_order

    return HttpResponse()


class QuestionDelete(EventPermissionRequiredMixin, DeleteView):
    model = Question
    template_name = 'pretixcontrol/items/question_delete.html'
    permission = 'can_change_items'
    context_object_name = 'question'

    def get_object(self, queryset=None) -> Question:
        try:
            return self.request.event.questions.get(id=self.kwargs['question'])
        except Question.DoesNotExist:
            raise Http404(_('The requested question does not exist.'))

    def get_context_data(self, *args, **kwargs) -> dict:
        context = super().get_context_data(*args, **kwargs)
        context['dependent'] = list(self.get_object().products.all())
        return context

    @transaction.atomic
    def form_valid(self, form):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.log_action(action='pretix.event.question.deleted', user=self.request.user)
        self.object.delete()
        messages.success(self.request, _('The selected question has been deleted.'))
        return HttpResponseRedirect(success_url)

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products.questions',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


class DescriptionDelete(QuestionDelete):
    template_name = 'pretixcontrol/items/desciption_delete.html'


class QuestionMixin:
    @cached_property
    def formset(self):
        formsetclass = inlineformset_factory(
            Question,
            QuestionOption,
            form=QuestionOptionForm,
            formset=I18nFormSet,
            can_order=True,
            can_delete=True,
            extra=0,
        )
        return formsetclass(
            self.request.POST if self.request.method == 'POST' else None,
            queryset=(
                QuestionOption.objects.filter(question=self.object) if self.object else QuestionOption.objects.none()
            ),
            event=self.request.event,
        )

    def save_formset(self, obj):
        if self.formset.is_valid():
            for form in self.formset.initial_forms:
                if form in self.formset.deleted_forms:
                    if not form.instance.pk:
                        continue
                    obj.log_action(
                        'pretix.event.question.option.deleted',
                        user=self.request.user,
                        data={'id': form.instance.pk},
                    )
                    form.instance.delete()
                    form.instance.pk = None

            forms = self.formset.ordered_forms + [
                ef
                for ef in self.formset.extra_forms
                if ef not in self.formset.ordered_forms and ef not in self.formset.deleted_forms
            ]
            for i, form in enumerate(forms):
                form.instance.position = i
                form.instance.question = obj
                created = not form.instance.pk
                form.save()
                if form.has_changed():
                    change_data = {k: form.cleaned_data.get(k) for k in form.changed_data}
                    change_data['id'] = form.instance.pk
                    obj.log_action(
                        'pretix.event.question.option.added' if created else 'pretix.event.question.option.changed',
                        user=self.request.user,
                        data=change_data,
                    )

            return True
        return False

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['formset'] = self.formset
        return ctx


class QuestionView(EventPermissionRequiredMixin, QuestionMixin, ChartContainingView, DetailView):
    model = Question
    template_name = 'pretixcontrol/items/question.html'
    permission = 'can_change_items'
    template_name_field = 'question'

    def get_answer_statistics(self):
        qs = QuestionAnswer.objects.filter(
            question=self.object,
            orderposition__isnull=False,
            orderposition__order__event=self.request.event,
        )
        s = self.request.GET.get('status', 'np')
        if s != '':
            if s == 'o':
                qs = qs.filter(
                    orderposition__order__status=Order.STATUS_PENDING,
                    orderposition__order__expires__lt=now().replace(hour=0, minute=0, second=0),
                )
            elif s == 'np':
                qs = qs.filter(
                    orderposition__order__status__in=[
                        Order.STATUS_PENDING,
                        Order.STATUS_PAID,
                    ]
                )
            elif s == 'ne':
                qs = qs.filter(
                    orderposition__order__status__in=[
                        Order.STATUS_PENDING,
                        Order.STATUS_EXPIRED,
                    ]
                )
            else:
                qs = qs.filter(orderposition__order__status=s)

        if s not in (Order.STATUS_CANCELED, ''):
            qs = qs.filter(orderposition__canceled=False)
        if self.request.GET.get('product', '') != '':
            i = self.request.GET.get('product', '')
            qs = qs.filter(orderposition__product_id__in=(i,))

        if self.object.type == Question.TYPE_FILE:
            qs = [
                {
                    'answer': gettext('File uploaded'),
                    'count': qs.filter(file__isnull=False).count(),
                }
            ]
        elif self.object.type in (Question.TYPE_CHOICE, Question.TYPE_CHOICE_MULTIPLE):
            qs = (
                qs.order_by('options')
                .values('options', 'options__answer')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
            for a in qs:
                a['alink'] = a['options']
                a['answer'] = str(a['options__answer'])
                del a['options__answer']
        elif self.object.type in (
            Question.TYPE_TIME,
            Question.TYPE_DATE,
            Question.TYPE_DATETIME,
        ):
            qs = qs.order_by('answer')
            model_cache = {a.answer: a for a in qs}
            qs = qs.values('answer').annotate(count=Count('id')).order_by('answer')
            for a in qs:
                a['alink'] = a['answer']
                a['answer'] = str(model_cache[a['answer']])
        else:
            qs = qs.order_by('answer').values('answer').annotate(count=Count('id')).order_by('-count')

            if self.object.type == Question.TYPE_BOOLEAN:
                for a in qs:
                    a['alink'] = a['answer']
                    a['answer_bool'] = a['answer'] == 'True'
                    a['answer'] = gettext('Yes') if a['answer'] == 'True' else gettext('No')
            elif self.object.type == Question.TYPE_COUNTRYCODE:
                for a in qs:
                    a['alink'] = a['answer']
                    a['answer'] = Country(a['answer']).name or a['answer']

        r = list(qs)
        total = sum(a['count'] for a in r)
        for a in r:
            a['percentage'] = (a['count'] / total * 100.0) if total else 0
        return r

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['products'] = self.object.products.all()
        stats = self.get_answer_statistics()
        ctx['stats'] = stats
        ctx['stats_json'] = json.dumps(stats)
        return ctx

    def get_object(self, queryset=None) -> Question:
        try:
            return self.request.event.questions.get(id=self.kwargs['question'])
        except Question.DoesNotExist:
            raise Http404(_('The requested question does not exist.'))

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products.questions',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


class QuestionUpdate(EventPermissionRequiredMixin, QuestionMixin, UpdateView):
    model = Question
    form_class = QuestionForm
    template_name = 'pretixcontrol/items/question_edit.html'
    permission = 'can_change_items'
    context_object_name = 'question'

    def get_object(self, queryset=None) -> Question:
        try:
            return self.request.event.questions.get(id=self.kwargs['question'])
        except Question.DoesNotExist:
            raise Http404(_('The requested question does not exist.'))

    @transaction.atomic
    def form_valid(self, form):
        if form.cleaned_data.get('type') in ('M', 'C'):
            if not self.save_formset(self.get_object()):
                return self.get(self.request, *self.args, **self.kwargs)

        if form.has_changed():
            self.object.log_action(
                'pretix.event.question.changed',
                user=self.request.user,
                data={k: form.cleaned_data.get(k) for k in form.changed_data},
            )
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products.questions',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class DescriptionUpdate(QuestionUpdate):
    form_class = DescriptionForm
    template_name = 'pretixcontrol/items/description_edit.html'


class QuestionCreate(EventPermissionRequiredMixin, QuestionMixin, CreateView):
    model = Question
    form_class = QuestionForm
    template_name = 'pretixcontrol/items/question_edit.html'
    permission = 'can_change_items'
    context_object_name = 'question'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = Question(event=self.request.event)
        return kwargs

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products.questions',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    def get_object(self, **kwargs):
        return None

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)

    @transaction.atomic
    def form_valid(self, form):
        if form.cleaned_data.get('type') in ('M', 'C'):
            if not self.formset.is_valid():
                return self.get(self.request, *self.args, **self.kwargs)

        messages.success(self.request, _('The new question has been created.'))
        ret = super().form_valid(form)
        form.instance.log_action(
            'pretix.event.question.added',
            user=self.request.user,
            data=dict(form.cleaned_data),
        )

        if form.cleaned_data.get('type') in ('M', 'C'):
            self.save_formset(form.instance)

        return ret


class DescriptionCreate(QuestionCreate):
    form_class = DescriptionForm
    template_name = 'pretixcontrol/items/description_edit.html'


@event_permission_required('can_view_items')
def question_options_ajax(request, organizer, event, question):
    try:
        question_obj = request.event.questions.get(id=question)
        
        if question_obj.type == Question.TYPE_BOOLEAN:
            options = [
                {'identifier': 'True', 'answer': str(_('Yes'))},
                {'identifier': 'False', 'answer': str(_('No'))}
            ]
        else:
            options = []
            for option in question_obj.options.all():
                options.append({
                    'identifier': option.identifier,
                    'answer': str(option.answer)
                })
        
        return JsonResponse({
            'type': question_obj.type,
            'options': options
        })
    except Question.DoesNotExist:
        return JsonResponse({'error': 'Question not found'}, status=404)


class QuotaList(PaginationMixin, ListView):
    model = Quota
    context_object_name = 'quotas'
    template_name = 'pretixcontrol/items/quotas.html'

    def get_queryset(self):
        qs = self.request.event.quotas.prefetch_related(
            Prefetch(
                'products',
                queryset=Product.objects.annotate(
                    has_variations=Exists(ProductVariation.objects.filter(product=OuterRef('pk')))
                ),
                to_attr='cached_products',
            ),
            'variations',
            'variations__product',
            Prefetch('subevent', queryset=self.request.event.subevents.all()),
        )
        if self.request.GET.get('subevent', '') != '':
            s = self.request.GET.get('subevent', '')
            qs = qs.filter(subevent_id=s)

        valid_orders = {
            '-date': ('-subevent__date_from', 'name'),
            'date': ('subevent__date_from', '-name'),
            'size': ('size', 'name'),
            '-size': ('-size', '-name'),
            'name': ('name',),
            '-name': ('-name',),
        }

        if self.request.GET.get('ordering', '-date') in valid_orders:
            qs = qs.order_by(*valid_orders[self.request.GET.get('ordering', '-date')])

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        qa = QuotaAvailability()
        qa.queue(*ctx['quotas'])
        qa.compute()
        for quota in ctx['quotas']:
            quota.cached_avail = qa.results[quota]

        return ctx


class QuotaCreate(EventPermissionRequiredMixin, CreateView):
    model = Quota
    form_class = QuotaForm
    template_name = 'pretixcontrol/items/quota_edit.html'
    permission = 'can_change_items'
    context_object_name = 'quota'

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products.quotas',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )

    @transaction.atomic
    def form_valid(self, form):
        form.instance.event = self.request.event
        messages.success(self.request, _('The new quota has been created.'))
        ret = super().form_valid(form)
        form.instance.log_action(
            'pretix.event.quota.added',
            user=self.request.user,
            data=dict(form.cleaned_data),
        )
        return ret

    @cached_property
    def copy_from(self):
        if self.request.GET.get('copy_from') and not getattr(self, 'object', None):
            try:
                return self.request.event.quotas.get(pk=self.request.GET.get('copy_from'))
            except Quota.DoesNotExist:
                pass

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        if self.copy_from:
            i = modelcopy(self.copy_from)
            i.pk = None
            kwargs['instance'] = i
            kwargs.setdefault('initial', {})
            kwargs['initial']['productvars'] = [str(i.pk) for i in self.copy_from.products.all()] + [
                '{}-{}'.format(v.product_id, v.pk) for v in self.copy_from.variations.all()
            ]
        else:
            kwargs['instance'] = Quota(event=self.request.event)
        return kwargs

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class QuotaView(ChartContainingView, DetailView):
    model = Quota
    template_name = 'pretixcontrol/items/quota.html'
    context_object_name = 'quota'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data()

        qa = QuotaAvailability(full_results=True)
        qa.queue(self.object)
        qa.compute()
        ctx['avail'] = qa.results[self.object]

        data = [
            {
                'label': gettext('Paid orders'),
                'value': qa.count_paid_orders[self.object],
                'sum': True,
            },
            {
                'label': gettext('Pending orders'),
                'value': qa.count_pending_orders[self.object],
                'sum': True,
            },
        ]
        if self.object.release_after_exit:
            data.append(
                {
                    'label': gettext('Exit scans'),
                    'value': -1 * qa.count_exited_orders[self.object],
                    'sum': True,
                }
            )

        data += [
            {
                'label': gettext('Vouchers and waiting list reservations'),
                'value': qa.count_vouchers[self.object],
                'sum': True,
            },
            {
                'label': gettext("Current user's carts"),
                'value': qa.count_cart[self.object],
                'sum': True,
            },
        ]

        sum_values = sum([d['value'] for d in data if d['sum']])
        s = self.object.size - sum_values if self.object.size is not None else gettext('Infinite')

        data.append(
            {
                'label': gettext('Available quota'),
                'value': s,
                'sum': False,
                'strong': True,
            }
        )
        data.append(
            {
                'label': gettext('Waiting list (pending)'),
                'value': qa.count_waitinglist[self.object],
                'sum': False,
            }
        )

        if self.object.size is not None:
            data.append(
                {
                    'label': gettext('Currently for sale'),
                    'value': ctx['avail'][1],
                    'sum': False,
                    'strong': True,
                }
            )

        for d in data:
            if isinstance(d.get('value', 0), int) and d.get('value', 0) < 0:
                d['value_abs'] = abs(d['value'])
        ctx['quota_chart_data'] = json.dumps([r for r in data if r.get('sum') and r['value'] >= 0])
        ctx['quota_table_rows'] = list(data)
        ctx['quota_overbooked'] = sum_values - self.object.size if self.object.size is not None else 0

        ctx['has_plugins'] = False
        res = (
            Quota.AVAILABILITY_GONE
            if self.object.size is not None and self.object.size - sum_values <= 0
            else Quota.AVAILABILITY_OK,
            self.object.size - sum_values if self.object.size is not None else None,
        )
        for recv, resp in quota_availability.send(
            sender=self.request.event,
            quota=self.object,
            result=res,
            count_waitinglist=True,
        ):
            if resp != res:
                ctx['has_plugins'] = True

        ctx['has_ignore_vouchers'] = Voucher.objects.filter(
            Q(allow_ignore_quota=True)
            & Q(Q(valid_until__isnull=True) | Q(valid_until__gte=now()))
            & Q(
                (
                    (  # Orders for products which do not have any variations
                        Q(variation__isnull=True)
                        & Q(
                            product_id__in=Quota.products.through.objects.filter(quota_id=self.object.pk).values_list(
                                'product_id', flat=True
                            )
                        )
                    )
                    | (  # Orders for products which do have any variations
                        Q(
                            variation__in=Quota.variations.through.objects.filter(quota_id=self.object.pk).values_list(
                                'productvariation_id', flat=True
                            )
                        )
                    )
                )
                | Q(quota=self.object)
            )
            & Q(redeemed__lt=F('max_usages'))
        ).exists()
        if self.object.closed:
            qa = QuotaAvailability(ignore_closed=True)
            qa.queue(self.object)
            qa.compute()
            ctx['closed_and_sold_out'] = qa.results[self.object][0] <= Quota.AVAILABILITY_ORDERED

        return ctx

    def get_object(self, queryset=None) -> Quota:
        try:
            return self.request.event.quotas.get(id=self.kwargs['quota'])
        except Quota.DoesNotExist:
            raise Http404(_('The requested quota does not exist.'))

    def post(self, request, *args, **kwargs):
        if not request.user.has_event_permission(request.organizer, request.event, 'can_change_items', request):
            raise PermissionDenied()
        quota = self.get_object()
        if 'reopen' in request.POST:
            quota.closed = False
            quota.save(update_fields=['closed'])
            quota.log_action('pretix.event.quota.opened', user=request.user)
            messages.success(request, _('The quota has been re-opened.'))
        if 'disable' in request.POST:
            quota.closed = False
            quota.close_when_sold_out = False
            quota.save(update_fields=['closed', 'close_when_sold_out'])
            quota.log_action('pretix.event.quota.opened', user=request.user)
            quota.log_action(
                'pretix.event.quota.changed',
                user=self.request.user,
                data={'close_when_sold_out': False},
            )
            messages.success(request, _('The quota has been re-opened and will not close again.'))
        return redirect(
            reverse(
                'control:event.products.quotas.show',
                kwargs={
                    'organizer': self.request.event.organizer.slug,
                    'event': self.request.event.slug,
                    'quota': quota.pk,
                },
            )
        )


class QuotaUpdate(EventPermissionRequiredMixin, UpdateView):
    model = Quota
    form_class = QuotaForm
    template_name = 'pretixcontrol/items/quota_edit.html'
    permission = 'can_change_items'
    context_object_name = 'quota'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data()
        return ctx

    def get_object(self, queryset=None) -> Quota:
        try:
            return self.request.event.quotas.get(id=self.kwargs['quota'])
        except Quota.DoesNotExist:
            raise Http404(_('The requested quota does not exist.'))

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))
        if form.has_changed():
            self.object.log_action(
                'pretix.event.quota.changed',
                user=self.request.user,
                data={k: form.cleaned_data.get(k) for k in form.changed_data},
            )
            if (form.initial.get('subevent') and not form.instance.subevent) or (
                form.instance.subevent and form.initial.get('subevent') != form.instance.subevent.pk
            ):
                if form.initial.get('subevent'):
                    se = SubEvent.objects.get(event=self.request.event, pk=form.initial.get('subevent'))
                    se.log_action(
                        'pretix.subevent.quota.deleted',
                        user=self.request.user,
                        data={'id': form.instance.pk},
                    )
                if form.instance.subevent:
                    form.instance.subevent.log_action(
                        'pretix.subevent.quota.added',
                        user=self.request.user,
                        data={'id': form.instance.pk},
                    )
            form.instance.rebuild_cache()
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products.quotas.show',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
                'quota': self.object.pk,
            },
        )

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class QuotaDelete(EventPermissionRequiredMixin, DeleteView):
    model = Quota
    template_name = 'pretixcontrol/items/quota_delete.html'
    permission = 'can_change_items'
    context_object_name = 'quota'

    def get_object(self, queryset=None) -> Quota:
        try:
            return self.request.event.quotas.get(id=self.kwargs['quota'])
        except Quota.DoesNotExist:
            raise Http404(_('The requested quota does not exist.'))

    def get_context_data(self, *args, **kwargs) -> dict:
        context = super().get_context_data(*args, **kwargs)
        context['dependent'] = list(self.object.products.all())
        context['vouchers'] = self.object.vouchers.count()
        return context

    @transaction.atomic
    def form_valid(self, form):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.log_action(action='pretix.event.quota.deleted', user=self.request.user)
        self.object.delete()
        messages.success(self.request, _('The selected quota has been deleted.'))
        return HttpResponseRedirect(success_url)

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products.quotas',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


class ProductDetailMixin(SingleObjectMixin):
    model = Product
    context_object_name = 'product'

    def get_object(self, queryset=None) -> Product:
        try:
            if not hasattr(self, 'object') or not self.object:
                self.product = self.request.event.products.get(id=self.kwargs['product'])
                self.object = self.product
            return self.object
        except Product.DoesNotExist:
            raise Http404(_('The requested product does not exist.'))


class MetaDataEditorMixin:
    meta_form = ProductMetaValueForm
    meta_model = ProductMetaValue

    @cached_property
    def meta_forms(self):
        if hasattr(self, 'object') and self.object:
            val_instances = {v.property_id: v for v in self.object.meta_values.all()}
        else:
            val_instances = {}

        formlist = []

        for p in self.request.event.product_meta_properties.all():
            formlist.append(self._make_meta_form(p, val_instances))
        return formlist

    def _make_meta_form(self, p, val_instances):
        return self.meta_form(
            prefix='prop-{}'.format(p.pk),
            property=p,
            instance=val_instances.get(p.pk, self.meta_model(property=p, product=self.object)),
            data=(self.request.POST if self.request.method == 'POST' else None),
        )

    def save_meta(self):
        for f in self.meta_forms:
            if f.cleaned_data.get('value'):
                f.save()
            elif f.instance and f.instance.pk:
                f.instance.delete()


class ProductCreate(EventPermissionRequiredMixin, CreateView):
    form_class = ProductCreateForm
    template_name = 'pretixcontrol/item/create.html'
    permission = 'can_change_items'

    def get_success_url(self) -> str:
        return reverse(
            'control:event.product',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
                'product': self.object.id,
            },
        )

    @cached_property
    def copy_from(self):
        if self.request.GET.get('copy_from') and not getattr(self, 'object', None):
            try:
                return self.request.event.products.get(pk=self.request.GET.get('copy_from'))
            except Product.DoesNotExist:
                pass

    def get_initial(self):
        initial = super().get_initial()
        trs = list(self.request.event.tax_rules.all())
        if len(trs) == 1:
            initial['tax_rule'] = trs[0]

        if self.copy_from:
            fields = (
                'name',
                'internal_name',
                'category',
                'admission',
                'default_price',
                'tax_rule',
            )
            for f in fields:
                initial[f] = getattr(self.copy_from, f)
            initial['copy_from'] = self.copy_from
            initial['has_variations'] = self.copy_from.variations.exists()

        return initial

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))

        ret = super().form_valid(form)
        form.instance.log_action(
            'eventyay.event.product.added',
            user=self.request.user,
            data={
                k: (
                    form.cleaned_data.get(k).name
                    if isinstance(form.cleaned_data.get(k), File)
                    else form.cleaned_data.get(k)
                )
                for k in form.changed_data
            },
        )
        return ret

    def get_form_kwargs(self):
        """
        Returns the keyword arguments for instantiating the form.
        """
        newinst = Product(event=self.request.event)
        kwargs = super().get_form_kwargs()
        kwargs.update({'instance': newinst, 'user': self.request.user})
        return kwargs

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)


class ProductUpdateGeneral(ProductDetailMixin, EventPermissionRequiredMixin, MetaDataEditorMixin, UpdateView):
    form_class = ProductUpdateForm
    template_name = 'pretixcontrol/item/index.html'
    permission = 'can_change_items'

    @cached_property
    def plugin_forms(self):
        forms = []
        for rec, resp in product_forms.send(sender=self.request.event, product=self.product, request=self.request):
            if isinstance(resp, (list, tuple)):
                forms.extend(resp)
            else:
                forms.append(resp)
        return forms

    def get_success_url(self) -> str:
        return reverse(
            'control:event.product',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
                'product': self.get_object().id,
            },
        )

    def is_valid(self, form):
        v = (
            form.is_valid()
            and all(f.is_valid() for f in self.plugin_forms)
            and all(f.is_valid() for f in self.formsets.values())
        )
        if v and form.cleaned_data['category'] and form.cleaned_data['category'].is_addon:
            addons = self.formsets['addons'].ordered_forms + [
                ef
                for ef in self.formsets['addons'].extra_forms
                if ef not in self.formsets['addons'].ordered_forms and ef not in self.formsets['addons'].deleted_forms
            ]
            if addons:
                messages.error(
                    self.request,
                    _('You cannot add add-ons to a product that is only available as an add-on itself.'),
                )
                v = False

            bundles = [ef for ef in self.formsets['bundles'].forms if ef not in self.formsets['bundles'].deleted_forms]
            if bundles:
                messages.error(
                    self.request,
                    _('You cannot add bundles to a product that is only available as an add-on itself.'),
                )
                v = False
        return v

    def post(self, request, *args, **kwargs):
        self.get_object()
        form = self.get_form()
        if self.is_valid(form) and all([f.is_valid() for f in self.meta_forms]):
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def save_formset(self, key, log_base, attr='product', order=True, serializer=None, rm_verb='removed'):
        for form in self.formsets[key].deleted_forms:
            if not form.instance.pk:
                continue
            d = {'id': form.instance.pk}
            if serializer:
                d.update(serializer(form.instance).data)
            self.get_object().log_action(
                'eventyay.event.product.{}.{}'.format(log_base, rm_verb),
                user=self.request.user,
                data=d,
            )
            form.instance.delete()
            form.instance.pk = None

        if order:
            forms = self.formsets[key].ordered_forms + [
                ef
                for ef in self.formsets[key].extra_forms
                if ef not in self.formsets[key].ordered_forms and ef not in self.formsets[key].deleted_forms
            ]
        else:
            forms = [ef for ef in self.formsets[key].forms if ef not in self.formsets[key].deleted_forms]
        for i, form in enumerate(forms):
            if order:
                form.instance.position = i
            setattr(form.instance, attr, self.get_object())
            created = not form.instance.pk
            form.save()
            if form.has_changed() and any(a for a in form.changed_data if a != 'ORDER'):
                change_data = {k: form.cleaned_data.get(k) for k in form.changed_data}
                if key == 'variations':
                    change_data['value'] = form.instance.value
                change_data['id'] = form.instance.pk
                self.get_object().log_action(
                    'eventyay.event.product.{}.changed'.format(log_base)
                    if not created
                    else 'eventyay.event.product.{}.added'.format(log_base),
                    user=self.request.user,
                    data=change_data,
                )

    @transaction.atomic
    def form_valid(self, form):
        self.save_meta()
        messages.success(self.request, _('Your changes have been saved.'))
        if form.has_changed() or any(f.has_changed() for f in self.plugin_forms):
            data = {k: form.cleaned_data.get(k) for k in form.changed_data}
            for f in self.plugin_forms:
                data.update(
                    {
                        k: (
                            f.cleaned_data.get(k).name
                            if isinstance(f.cleaned_data.get(k), File)
                            else f.cleaned_data.get(k)
                        )
                        for k in f.changed_data
                    }
                )
            self.object.log_action('eventyay.event.product.changed', user=self.request.user, data=data)
            invalidate_cache.apply_async(kwargs={'event': self.request.event.pk, 'product': self.object.pk})
        for f in self.plugin_forms:
            f.save()

        for k, v in self.formsets.items():
            if k == 'variations':
                self.save_formset(
                    'variations',
                    'variation',
                    serializer=ProductVariationSerializer,
                    rm_verb='deleted',
                )
            elif k == 'addons':
                self.save_formset('addons', 'addons', 'base_product', serializer=ProductAddOnSerializer)
            elif k == 'bundles':
                self.save_formset(
                    'bundles',
                    'bundles',
                    'base_product',
                    order=False,
                    serializer=ProductBundleSerializer,
                )
            else:
                v.save()

        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('We could not save your changes. See below for details.'))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['plugin_forms'] = self.plugin_forms
        ctx['meta_forms'] = self.meta_forms
        ctx['formsets'] = self.formsets

        if not ctx['product'].active and ctx['product'].bundled_with.count() > 0:
            messages.info(
                self.request,
                _(
                    'You disabled this product, but it is still part of a product bundle. '
                    "Your participants won't be able to buy the bundle unless you remove this "
                    'product from it.'
                ),
            )

        return ctx

    @cached_property
    def formsets(self):
        f = OrderedDict(
            [
                (
                    'variations',
                    inlineformset_factory(
                        Product,
                        ProductVariation,
                        form=ProductVariationForm,
                        formset=ProductVariationsFormSet,
                        can_order=True,
                        can_delete=True,
                        extra=0,
                    )(
                        self.request.POST if self.request.method == 'POST' else None,
                        queryset=ProductVariation.objects.filter(product=self.get_object()),
                        event=self.request.event,
                        prefix='variations',
                    ),
                ),
                (
                    'addons',
                    inlineformset_factory(
                        Product,
                        ProductAddOn,
                        form=ProductAddOnForm,
                        formset=ProductAddOnsFormSet,
                        can_order=True,
                        can_delete=True,
                        extra=0,
                    )(
                        self.request.POST if self.request.method == 'POST' else None,
                        queryset=ProductAddOn.objects.filter(base_product=self.get_object()),
                        event=self.request.event,
                        prefix='addons',
                    ),
                ),
                (
                    'bundles',
                    inlineformset_factory(
                        Product,
                        ProductBundle,
                        form=ProductBundleForm,
                        formset=ProductBundleFormSet,
                        fk_name='base_product',
                        can_order=False,
                        can_delete=True,
                        extra=0,
                    )(
                        self.request.POST if self.request.method == 'POST' else None,
                        queryset=ProductBundle.objects.filter(base_product=self.get_object()),
                        event=self.request.event,
                        product=self.product,
                        prefix='bundles',
                    ),
                ),
            ]
        )
        if not self.object.has_variations:
            del f['variations']

        i = 0
        for rec, resp in product_formsets.send(sender=self.request.event, product=self.product, request=self.request):
            if isinstance(resp, (list, tuple)):
                for k in resp:
                    f['p-{}'.format(i)] = k
                    i += 1
            else:
                f['p-{}'.format(i)] = resp
                i += 1
        return f


class ProductDelete(EventPermissionRequiredMixin, DeleteView):
    model = Product
    template_name = 'pretixcontrol/item/delete.html'
    permission = 'can_change_items'
    context_object_name = 'product'

    def get_context_data(self, *args, **kwargs) -> dict:
        context = super().get_context_data(*args, **kwargs)
        context['possible'] = self.is_allowed()
        context['vouchers'] = self.object.vouchers.count()
        return context

    def is_allowed(self) -> bool:
        return not self.get_object().orderposition_set.exists()

    def get_object(self, queryset=None) -> Product:
        if not hasattr(self, 'object') or not self.object:
            try:
                self.object = self.request.event.products.get(id=self.kwargs['product'])
            except Product.DoesNotExist:
                raise Http404(_('The requested product does not exist.'))
        return self.object

    @transaction.atomic
    def form_valid(self, form):
        success_url = self.get_success_url()
        o = self.get_object()
        if o.allow_delete():
            CartPosition.objects.filter(addon_to__product=self.get_object()).delete()
            self.get_object().cartposition_set.all().delete()
            self.get_object().log_action('eventyay.event.product.deleted', user=self.request.user)
            self.get_object().delete()
            messages.success(self.request, _('The selected product has been deleted.'))
            return HttpResponseRedirect(success_url)
        else:
            o = self.get_object()
            o.active = False
            o.save()
            o.log_action(
                'eventyay.event.product.changed',
                user=self.request.user,
                data={'active': False},
            )
            messages.success(self.request, _('The selected product has been deactivated.'))
            return HttpResponseRedirect(success_url)

    def get_success_url(self) -> str:
        return reverse(
            'control:event.products',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )


@event_permission_required('can_change_items')
def question_options_ajax(request, organizer, event, question):
    try:
        question_obj = request.event.questions.get(id=question)
        if question_obj.type == Question.TYPE_BOOLEAN:
            options = [
                {'identifier': 'True', 'answer': str(_('Yes'))},
                {'identifier': 'False', 'answer': str(_('No'))}
            ]
        else:
            options = []
            for option in question_obj.options.all():
                options.append({
                    'identifier': option.identifier,
                    'answer': str(option.answer)
                })
        
        return JsonResponse({
            'type': question_obj.type,
            'options': options
        })
    except Question.DoesNotExist:
        return JsonResponse({'error': 'Question not found'}, status=404)
