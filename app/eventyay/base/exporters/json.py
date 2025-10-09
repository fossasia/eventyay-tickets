import json
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.dispatch import receiver

from ..exporter import BaseExporter
from ..signals import register_data_exporters


class JSONExporter(BaseExporter):
    identifier = 'json'
    verbose_name = 'Order data (JSON)'

    def render(self, form_data):
        jo = {
            'event': {
                'name': str(self.event.name),
                'slug': self.event.slug,
                'organizer': {
                    'name': str(self.event.organizer.name),
                    'slug': self.event.organizer.slug,
                },
                'categories': [
                    {
                        'id': category.id,
                        'name': str(category.name),
                        'internal_name': category.internal_name,
                    }
                    for category in self.event.categories.all()
                ],
                'products': [
                    {
                        'id': product.id,
                        'name': str(product.name),
                        'internal_name': str(product.internal_name),
                        'category': product.category_id,
                        'price': product.default_price,
                        'tax_rate': product.tax_rule.rate if product.tax_rule else Decimal('0.00'),
                        'tax_name': str(product.tax_rule.name) if product.tax_rule else None,
                        'admission': product.admission,
                        'active': product.active,
                        'variations': [
                            {
                                'id': variation.id,
                                'active': variation.active,
                                'price': variation.default_price
                                if variation.default_price is not None
                                else product.default_price,
                                'name': str(variation),
                            }
                            for variation in product.variations.all()
                        ],
                    }
                    for product in self.event.products.select_related('tax_rule').prefetch_related('variations')
                ],
                'questions': [
                    {
                        'id': question.id,
                        'question': str(question.question),
                        'type': question.type,
                    }
                    for question in self.event.questions.all()
                ],
                'orders': [
                    {
                        'code': order.code,
                        'status': order.status,
                        'user': order.email,
                        'datetime': order.datetime,
                        'fees': [
                            {
                                'type': fee.fee_type,
                                'description': fee.description,
                                'value': fee.value,
                            }
                            for fee in order.fees.all()
                        ],
                        'total': order.total,
                        'positions': [
                            {
                                'id': position.id,
                                'product': position.product_id,
                                'variation': position.variation_id,
                                'price': position.price,
                                'attendee_name': position.attendee_name,
                                'attendee_email': position.attendee_email,
                                'secret': position.secret,
                                'addon_to': position.addon_to_id,
                                'answers': [
                                    {
                                        'question': answer.question_id,
                                        'answer': answer.answer,
                                    }
                                    for answer in position.answers.all()
                                ],
                            }
                            for position in order.positions.all()
                        ],
                    }
                    for order in self.event.orders.all().prefetch_related('positions', 'positions__answers', 'fees')
                ],
                'quotas': [
                    {
                        'id': quota.id,
                        'size': quota.size,
                        'products': [product.id for product in quota.products.all()],
                        'variations': [variation.id for variation in quota.variations.all()],
                    }
                    for quota in self.event.quotas.all().prefetch_related('products', 'variations')
                ],
            }
        }

        return (
            '{}_pretixdata.json'.format(self.event.slug),
            'application/json',
            json.dumps(jo, cls=DjangoJSONEncoder),
        )


@receiver(register_data_exporters, dispatch_uid='exporter_json')
def register_json_export(sender, **kwargs):
    return JSONExporter
