import base64
import hashlib
import json
import logging
import time
import urllib.parse
import uuid
from typing import List, Optional

import jwt
import requests
from cryptography.fernet import Fernet
from django.core.cache import cache

logger = logging.getLogger("pretix.plugins.paypal")


class PaypalRequestHandler:
    def __init__(self, settings):
        # settings contain client_id and secret_key
        self.settings = settings
        if settings.connect_client_id and not settings.secret:
            # In case set paypal info in global settings
            self.connect_client_id = self.settings.connect_client_id
            self.secret_key = self.settings.connect_secret_key
        else:
            # In case organizer set their own info
            self.connect_client_id = self.settings.get("client_id")
            self.secret_key = self.settings.get("secret")

        # Redis cache key
        self.set_cache_token_key()

        # Endpoints to communicate with paypal
        if self.settings.connect_endpoint == "sandbox":
            self.endpoint = "https://api-m.sandbox.paypal.com"
        else:
            self.endpoint = "https://api-m.paypal.com"

        self.oauth_url = urllib.parse.urljoin(self.endpoint, "v1/oauth2/token")
        self.partner_referrals_url = urllib.parse.urljoin(
            self.endpoint, "/v2/customer/partner-referrals"
        )
        self.order_url = urllib.parse.urljoin(
            self.endpoint, "v2/checkout/orders/{order_id}"
        )
        self.create_order_url = urllib.parse.urljoin(
            self.endpoint, "v2/checkout/orders"
        )
        self.capture_order_url = urllib.parse.urljoin(
            self.endpoint, "v2/checkout/orders/{order_id}/capture"
        )
        self.refund_detail_url = urllib.parse.urljoin(
            self.endpoint, "v2/payments/refunds/{refund_id}"
        )
        self.refund_payment_url = urllib.parse.urljoin(
            self.endpoint, "v2/payments/captures/{capture_id}/refund"
        )
        self.verify_webhook_url = urllib.parse.urljoin(
            self.endpoint, "/v1/notifications/verify-webhook-signature"
        )

        self.paypal_request_id = self.get_paypal_request_id()

    def request(
        self,
        url: str,
        method: str,
        data=None,
        params=None,
        headers=None,
        timeout=15,
    ) -> dict:

        reason = ""
        response_data = {}
        try:
            if method == "GET":
                response = requests.get(
                    url, data=data, params=params, headers=headers, timeout=timeout
                )
            elif method == "POST":
                response = requests.post(
                    url, data=data, params=params, headers=headers, timeout=timeout
                )
            elif method == "PATCH":
                # Patch request return empty body
                requests.patch(
                    url, data=data, params=params, headers=headers, timeout=timeout
                )
                return {}

            # In case request failed, capture specific reason
            reason = response.reason
            response.raise_for_status()

            if "application/json" not in response.headers.get("Content-Type"):
                raise requests.exceptions.JSONDecodeError(
                    msg=f"Reponse of request to {url} is not json parsable."
                )

            response_data["response"] = response.json()
            return response_data
        except requests.exceptions.JSONDecodeError as e:
            response_data["errors"] = {
                "type": "JSONDecodeError",
                "reason": reason,
                "exception": e,
            }
            return response_data
        except requests.exceptions.ReadTimeout as e:
            response_data["errors"] = {
                "type": "ReadTimeout",
                "reason": reason,
                "exception": e,
            }
            return response_data
        except requests.exceptions.RequestException as e:
            response_data["errors"] = {
                "type": "Ambiguous",
                "reason": reason,
                "exception": e,
            }
            return response_data

    @staticmethod
    def check_expired_token(access_token_data: dict, buffer_time: int = 300) -> bool:
        current_time = time.time()
        expiration_time = (
            access_token_data["created_at"] + access_token_data["expires_in"]
        )
        is_expired = (current_time + buffer_time) > expiration_time
        return is_expired

    @staticmethod
    def encode_b64(connect_client_id: str, connect_secret_key: str) -> str:
        """Encode client_key:secret_key to base64"""
        key = f"{connect_client_id}:{connect_secret_key}"
        key_bytes = key.encode("ascii")
        base64_bytes = base64.b64encode(key_bytes)
        base64_string = base64_bytes.decode("ascii")
        return base64_string

    def set_cache_token_key(self) -> str:
        if self.connect_client_id and self.secret_key:
            hash_code = hashlib.sha256(
                "".join([self.connect_client_id, self.secret_key]).encode()
            ).hexdigest()
            self.cache_token_key = "paypal_token_hash_{}".format(hash_code)
            # Fernet key must be 32 urlsafe b64encode
            self.fernet = Fernet(base64.urlsafe_b64encode(hash_code[:32].encode()))

    def get_paypal_request_id(self):
        """
        https://developer.paypal.com/api/rest/reference/idempotency/
        To avoid duplicate requests, set an id in each instance
        Used in: create order, capture order, refund payment
        """
        return str(uuid.uuid4())

    def get_paypal_auth_assertion(self, merchant_id: str) -> str:
        """
        https://developer.paypal.com/docs/multiparty/issue-refund/
        https://developer.paypal.com/docs/api/payments/v2/#captures_refund
        To issue a refund on behalf of the merchant,
        Paypal-Auth-Assertion is required
        """
        if merchant_id is None:
            return ""

        return jwt.encode(
            key=None,
            algorithm=None,
            payload={"iss": self.connect_client_id, "payer_id": merchant_id},
        )

    def get_access_token(self) -> Optional[str]:
        """
        https://developer.paypal.com/api/rest/authentication/
        Get access token data from cache and check expiration
        If expired, request for new one, then set it back in cache
        Scope: order, invoice, ...
        """

        def request_new_access_token():
            access_token_response = self.request(
                url=self.oauth_url,
                method="POST",
                headers={
                    "Authorization": f"Basic {self.encode_b64(self.connect_client_id, self.secret_key)}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )

            if access_token_response.get("errors"):
                errors = access_token_response.get("errors")
                logger.error(
                    "Error getting access token from Paypal: {}".format(
                        errors["reason"]
                    )
                )
                return None

            access_token_data = access_token_response.get("response")
            # Add this key value to check for token expiration later
            access_token_data["created_at"] = time.time()
            # Encrypt access token data and set in cache
            encrypted_access_token_data = self.fernet.encrypt(
                json.dumps(access_token_data).encode()
            )
            cache.set(self.cache_token_key, encrypted_access_token_data, 3600 * 2)
            return access_token_data

        # Check cache data
        encrypted_access_token_data = cache.get(self.cache_token_key)
        if encrypted_access_token_data is None:
            access_token_data = request_new_access_token()
        else:
            access_token_data = json.loads(
                self.fernet.decrypt(encrypted_access_token_data).decode()
            )

            if self.check_expired_token(access_token_data):
                access_token_data = request_new_access_token()

        access_token = access_token_data.get("access_token")
        return access_token

    def create_partner_referrals(self, data: dict) -> dict:
        """
        https://developer.paypal.com/docs/api/orders/v2/#orders_create
        """
        response = self.request(
            url=self.partner_referrals_url,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.get_access_token()}",
            },
            data=json.dumps(data),
        )
        return response

    def get_order(self, order_id: str) -> dict:
        """
        https://developer.paypal.com/docs/api/orders/v2/#orders_get
        """
        response = self.request(
            url=self.order_url.format(order_id=order_id),
            method="GET",
            headers={"Authorization": f"Bearer {self.get_access_token()}"},
        )
        return response

    def create_order(self, order_data: dict) -> dict:
        """
        https://developer.paypal.com/docs/api/orders/v2/#orders_create
        """
        response = self.request(
            url=self.create_order_url,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.get_access_token()}",
                "PayPal-Request-Id": self.paypal_request_id,
            },
            data=json.dumps(order_data),
        )
        return response

    def capture_order(self, order_id: str) -> dict:
        """
        https://developer.paypal.com/docs/api/orders/v2/#orders_capture
        """

        response = self.request(
            url=self.capture_order_url.format(order_id=order_id),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.get_access_token()}",
                "PayPal-Request-Id": self.paypal_request_id,
            },
        )
        return response

    def update_order(self, order_id: str, update_data: List[dict]) -> dict:
        """
        https://developer.paypal.com/docs/api/orders/v2/#orders_patch
        """

        response = self.request(
            url=self.order_url.format(order_id=order_id),
            method="PATCH",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.get_access_token()}",
            },
            data=json.dumps(update_data),
        )
        return response

    def get_refund_detail(self, refund_id: str, merchant_id: str) -> dict:
        """
        https://developer.paypal.com/docs/api/payments/v2/#refunds_get
        """

        response = self.request(
            url=self.refund_detail_url.format(refund_id=refund_id),
            method="GET",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.get_access_token()}",
                "PayPal-Auth-Assertion": self.get_paypal_auth_assertion(merchant_id),
            },
        )
        return response

    def refund_payment(
        self,
        capture_id: str,
        refund_data: dict,
        merchant_id: str = None,
    ) -> dict:
        """
        https://developer.paypal.com/docs/api/payments/v2/#captures_refund
        """
        response = self.request(
            url=self.refund_payment_url.format(capture_id=capture_id),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.get_access_token()}",
                "PayPal-Auth-Assertion": self.get_paypal_auth_assertion(merchant_id),
                "PayPal-Request-Id": self.paypal_request_id,
            },
            data=json.dumps(refund_data),
        )
        return response

    def verify_webhook_signature(self, data: dict) -> dict:
        """
        https://developer.paypal.com/docs/api/webhooks/v1/#verify-webhook-signature_post
        """
        response = self.request(
            url=self.verify_webhook_url,
            method="POST",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.get_access_token()}",
            },
        )
        return response
