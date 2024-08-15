import base64
import hashlib
import logging
import time
from datetime import datetime
from urllib.parse import urlencode, urljoin

import jwt
import requests
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from requests import RequestException

from pretix.multidomain.urlreverse import build_absolute_uri

logger = logging.getLogger(__name__)


def _urljoin(base, path):
    """
    Joins a base URL and a relative path to form a complete URL.
    Args:
        base (str): The base URL.
        path (str): The relative path to be joined with the base URL.
    Returns:
        str: The complete URL formed by joining the base URL and the relative path.
    """
    if not base.endswith("/"):
        base += "/"
    return urljoin(base, path)


def validate_config(config):
    """
    Validates and completes the OIDC configuration.

    Args:
        config (dict): A dictionary containing the OIDC configuration options.

    Returns:
        dict: The validated and completed OIDC configuration.

    Raises:
        ValidationError: If any required configuration option is missing or if the provider is incompatible.
    """
    required_keys = ["base_url", "client_id", "client_secret", "uid_field", "email_field", "scope"]
    missing_keys = [k for k in required_keys if not config.get(k)]
    if missing_keys:
        raise ValidationError(_('Missing option(s) "{name}".').format(name=", ".join(missing_keys)))

    conf_url = _urljoin(config["base_url"], ".well-known/openid-configuration")
    try:
        provider_resp = requests.get(conf_url, timeout=15)
        provider_resp.raise_for_status()
        provider_config = provider_resp.json()
    except (RequestException, ValueError) as e:
        raise ValidationError(_('Configuration from "{url}" is missing. message: "{error}".').format(
            url=conf_url,
            error=str(e)
        ))

    required_endpoints = ["authorization_endpoint", "userinfo_endpoint", "token_endpoint"]
    for endpoint in required_endpoints:
        if not provider_config.get(endpoint):
            raise ValidationError(_('Incompatible SSO provider: "{error}".').format(
                error=f"{endpoint} not set"
            ))

    if "code" not in provider_config.get("response_types_supported", []):
        raise ValidationError(_('SSO provider not compatibility: "{error}".').format(
            error=f"The provider supports these response types: {', '.join(provider_config.get('response_types_supported', []))}"
                  f". However, our application only supports the 'code' response type."
        ))

    if "query" not in provider_config.get("response_modes_supported", ["query", "fragment"]):
        raise ValidationError(_('SSO provider not compatibility: "{error}".').format(
            error=f"The provider can handle these response modes: {', '.join(provider_config.get('response_modes_supported', []))}"
                  f". However, our system only supports the 'query' mode."
        ))

    if "authorization_code" not in provider_config.get("grant_types_supported", ["authorization_code", "implicit"]):
        raise ValidationError(_('SSO provider not compatibility: "{error}".').format(
            error=f"The provider supports these grant types: {', '.join(provider_config.get('grant_types_supported', []))}"
                  f". However, our application only supports the 'authorization_code' grant type."
        ))

    if "openid" not in config["scope"].split(" "):
        raise ValidationError(_('You are not requesting "{scope}".').format(scope="openid"))

    for scope in config["scope"].split(" "):
        if scope not in provider_config.get("scopes_supported", []):
            raise ValidationError(
                _('Requesting scope "{scope}" is not supported: {scopes}.').format(
                    scope=scope,
                    scopes=", ".join(provider_config.get("scopes_supported", []))
                ))

    for k, v in config.items():
        if k.endswith('_field') and v:
            if v not in provider_config.get("claims_supported", []):
                raise ValidationError(
                    _('Requesting field "{field}" is not supported: {fields}.').format(
                        field=v,
                        fields=", ".join(provider_config.get("claims_supported", []))
                    ))

    config['provider_config'] = provider_config
    return config


def get_authorize_url(provider, state, redirect_uri):
    """
    Constructs the OIDC authorization URL.

    Args:
        provider: The OIDC provider containing configuration details.
        state (str): A unique state string to prevent CSRF attacks.
        redirect_uri (str): The URI to which the response will be sent.

    Returns:
        str: The constructed authorization URL.
    """
    # Retrieve the authorization endpoint from the provider's configuration
    endpoint = provider.configuration['provider_config']['authorization_endpoint']

    # Construct URL parameters
    params = {
        'response_type': 'code',
        'client_id': provider.configuration['client_id'],
        'scope': provider.configuration['scope'],
        'state': state,
        'redirect_uri': redirect_uri,
    }

    # Join the endpoint with encoded parameters
    url = urljoin(endpoint, '?' + urlencode(params))

    return url


def retrieve_user_profile(provider, code, redirect_uri):
    """
    Validates the OIDC authorization code and retrieves user information.

    Args:
        provider: The OIDC provider containing configuration details.
        code (str): The authorization code received from the OIDC provider.
        redirect_uri (str): The URI to which the response will be sent.

    Returns:
        dict: A dictionary containing the user's profile information.

    Raises:
        ValidationError: If any part of the authorization or user info retrieval process fails.
    """
    endpoint = provider.configuration['provider_config']['token_endpoint']
    params = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
    }
    try:
        resp = requests.post(
            endpoint,
            data=params,
            headers={
                'Accept': 'application/json',
            },
            auth=(
                provider.configuration['client_id'],
                provider.configuration['client_secret']
            ),
        )
        resp.raise_for_status()
        data = resp.json()
    except RequestException:
        logger.exception('Could not retrieve authorization token')
        raise ValidationError(
            _('Login failed. Error message: "{error}".').format(
                error='login provider not reachable',
            )
        )

    if 'access_token' not in data:
        raise ValidationError(
            _('Login failed. Error message: "{error}".').format(
                error='missing access token',
            )
        )

    endpoint = provider.configuration['provider_config']['userinfo_endpoint']
    try:
        resp = requests.get(
            endpoint,
            headers={
                'Authorization': f'Bearer {data["access_token"]}'
            },
        )
        resp.raise_for_status()
        userinfo = resp.json()
    except RequestException:
        logger.exception('Could not retrieve user info')
        raise ValidationError(
            _('Login failed. Error message: "{error}".').format(
                error='user info not reachable',
            )
        )

    if userinfo.get('email_verified') is False:
        raise ValidationError(_('Please verify your mail first.'))
    profile = {k[:-6]: userinfo.get(v) for k, v in provider.configuration.items() if k.endswith('_field')}

    missing_fields = [field for field in ['uid', 'email'] if not profile.get(field)]
    if missing_fields:
        raise ValidationError(
            _('Login failed. Error message: "{error}".').format(
                error=f'could not fetch user {", ".join(missing_fields)}',
            )
        )

    return profile


def _hash_scheme(value):
    """
    Hashes the input value using SHA-256, truncates the hash to half its length,
    and encodes it in URL-safe Base64.

    Args:
        value (str): The input string to be hashed.

    Returns:
        str: The URL-safe Base64 encoded hash of the input string, truncated to half its length.
    """
    # Compute SHA-256 hash of the input value
    digest = hashlib.sha256(value.encode()).digest()

    # Truncate the hash to half its length
    digest_truncated = digest[:len(digest) // 2]

    # Encode the truncated hash in URL-safe Base64 and remove padding
    encoded_value = base64.urlsafe_b64encode(digest_truncated).decode().rstrip("=")

    return encoded_value


def customer_claims(customer, scope):
    """
    Generates a dictionary of claims for the given customer based on the requested scope.

    Args:
        customer (Customer model): The customer object containing relevant information.
        scope (str): A space-separated string of scopes indicating which claims to include.

    Returns:
        dict: A dictionary containing the claims for the customer.
    """
    scope_set = set(scope.split(' '))
    claims = {
        'sub': customer.identifier,
        'locale': customer.locale,
    }

    if 'profile' in scope_set:
        if customer.name:
            claims['name'] = customer.name
        name_parts = customer.name_parts
        if 'given_name' in name_parts:
            claims['given_name'] = name_parts['given_name']
        if 'family_name' in name_parts:
            claims['family_name'] = name_parts['family_name']
        if 'middle_name' in name_parts:
            claims['middle_name'] = name_parts['middle_name']
        if 'calling_name' in name_parts:
            claims['nickname'] = name_parts['calling_name']

    if 'email' in scope_set and customer.email:
        claims['email'] = customer.email
        claims['email_verified'] = customer.is_verified

    if 'phone' in scope_set and customer.phone:
        claims['phone_number'] = customer.phone.as_international

    return claims


def _get_or_create_server_keypair(organizer):
    """
    Retrieves or creates an RSA key pair for the given organizer. If the keys do not exist, they are generated and stored.

    Args:
        organizer: The organizer object containing settings for SSO server keys.

    Returns:
        tuple: A tuple containing the private key and public key in PEM format.
    """
    # Check if the private key does not exist
    if not organizer.settings.sso_server_signing_key_rsa256_private:
        prkey = generate_private_key(key_size=4096, public_exponent=65537)
        pubkey = prkey.public_key()
        organizer.settings.sso_server_signing_key_rsa256_private = prkey.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        ).decode()

        # Store the public key in PEM format
        organizer.settings.sso_server_signing_key_rsa256_public = pubkey.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode()
    return organizer.settings.sso_server_signing_key_rsa256_private, organizer.settings.sso_server_signing_key_rsa256_public


def generate_id_token(customer, client, auth_time, nonce, scope, expires: datetime, scope_claims=False, with_code=None,
                      with_access_token=None):
    """
    Generates an ID token for the given customer and client.

    Args:
        customer: The customer object containing relevant information.
        client: The client object containing relevant information.
        auth_time (int): The authentication time as a Unix timestamp.
        nonce (str): A unique string to associate the token with the authentication request.
        scope (str): A space-separated string of scopes.
        expires (datetime): The expiration time of the token.
        scope_claims (bool): Whether to include claims based on the evaluated scope.
        with_code (str, optional): An optional authorization code to include in the token.
        with_access_token (str, optional): An optional access token to include in the token.

    Returns:
        str: The generated ID token as a JWT.
    """
    # Build the payload for the ID token
    payload = {
        'iss': build_absolute_uri(client.organizer, 'presale:organizer.index').rstrip('/'),
        'aud': client.client_id,
        'exp': int(expires.timestamp()),
        'iat': int(time.time()),
        'auth_time': auth_time,
        **customer_claims(customer, client.evaluated_scope(scope) if scope_claims else ''),
    }

    # Add optional claims if provided
    if nonce:
        payload['nonce'] = nonce
    if with_code:
        payload['c_hash'] = _hash_scheme(with_code)
    if with_access_token:
        payload['at_hash'] = _hash_scheme(with_access_token)

    # Get or create the server keypair for signing
    privkey, pubkey = _get_or_create_server_keypair(client.organizer)

    # Generate the ID token as a JWT
    return jwt.encode(
        payload,
        privkey,
        headers={
            "kid": hashlib.sha256(pubkey.encode()).hexdigest()[:16]
        },
        algorithm="RS256",
    )
