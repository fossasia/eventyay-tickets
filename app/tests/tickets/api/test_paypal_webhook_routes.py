import importlib.util

import pytest
from django.test import Client

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec('eventyay_paypal') is None,
    reason='eventyay_paypal is not installed',
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    'path',
    [
        '/_paypal/webhook',
        '/_paypal/webhook/',
        '/tickets/_paypal/webhook',
        '/tickets/_paypal/webhook/',
    ],
)
def test_paypal_payment_webhook_compat_paths_do_not_404(path):
    """PayPal webhooks must reach the plugin without APPEND_SLASH 301 redirects."""
    client = Client()
    response = client.post(path, data=b'{}', content_type='application/json')
    assert response.status_code != 404, response.content
    assert response.status_code not in (301, 302), response.get('Location')
    assert response.status_code == 400
