import jwt
from paypalcheckoutsdk.core import PayPalEnvironment as VendorPayPalEnvironment


class PayPalEnvironment(VendorPayPalEnvironment):
    """
    Represents a PayPal environment configuration.

    Attributes:
        client_id (str): PayPal client ID.
        client_secret (str): PayPal client secret.
        api_url (str): PayPal API URL. Defaults to sandbox API URL if not provided.
        web_url (str): PayPal web URL. Defaults to sandbox web URL if not provided.
        merchant_id (str): Optional merchant ID for authorization assertion.
        partner_id (str): Optional partner ID for authorization assertion.
    """

    def __init__(self, client_id, client_secret, api_url=None, web_url=None, merchant_id=None, partner_id=None):
        """
        Initialize a PayPal environment.

        Args:
            client_id (str): PayPal client ID.
            client_secret (str): PayPal client secret.
            api_url (str, optional): PayPal API URL. Defaults to sandbox API URL.
            web_url (str, optional): PayPal web URL. Defaults to sandbox web URL.
            merchant_id (str, optional): Merchant ID for authorization assertion.
            partner_id (str, optional): Partner ID for authorization assertion.
        """
        super().__init__(client_id, client_secret, api_url or VendorPayPalEnvironment.SANDBOX_API_URL,
                         web_url or VendorPayPalEnvironment.SANDBOX_WEB_URL)
        self.merchant_id = merchant_id
        self.partner_id = partner_id

    def authorization_assertion(self):
        """
        Generate a JWT authorization assertion for PayPal.

        Returns:
            str: JWT encoded authorization assertion if merchant_id is provided, otherwise an empty string.
        """
        if self.merchant_id:
            return jwt.encode(
                payload={
                    'iss': self.client_id,
                    'payer_id': self.merchant_id
                },
                key=None,
                algorithm=None,
            )
        return ""


class SandboxEnvironment(PayPalEnvironment):
    """
    Represents a PayPal sandbox environment configuration.

    Inherits:
        PayPalEnvironment
    """

    def __init__(self, client_id, client_secret, merchant_id=None, partner_id=None):
        """
        Initialize a PayPal sandbox environment.

        Args:
            client_id (str): PayPal client ID.
            client_secret (str): PayPal client secret.
            merchant_id (str, optional): Merchant ID for authorization assertion.
            partner_id (str, optional): Partner ID for authorization assertion.
        """
        super().__init__(client_id, client_secret, merchant_id=merchant_id, partner_id=partner_id)


class LiveEnvironment(PayPalEnvironment):
    """
    Represents a live PayPal environment configuration.

    Inherits:
        PayPalEnvironment
    """

    def __init__(self, client_id, client_secret, merchant_id, partner_id):
        """
        Initialize a live PayPal environment.

        Args:
            client_id (str): PayPal client ID.
            client_secret (str): PayPal client secret.
            merchant_id (str): Merchant ID for authorization assertion.
            partner_id (str): Partner ID for authorization assertion.
        """
        super().__init__(client_id, client_secret, api_url=VendorPayPalEnvironment.LIVE_API_URL,
                         web_url=VendorPayPalEnvironment.LIVE_WEB_URL, merchant_id=merchant_id, partner_id=partner_id)
