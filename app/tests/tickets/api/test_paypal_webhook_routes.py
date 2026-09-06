import pytest
from django.test import Client

pytest.importorskip('eventyay_paypal')


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
    assert response.status_code == 400
    assert response.get('Location') is None
