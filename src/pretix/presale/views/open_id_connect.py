import base64
import hashlib
import time
from binascii import unhexlify
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from Crypto.PublicKey import RSA
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse, HttpRequest
from django.shortcuts import redirect, render
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters

from pretix.base.customersso.open_id_connect import (
    _get_or_create_server_keypair, customer_claims, generate_id_token,
)
from pretix.base.models.customers import (
    CustomerSSOAccessToken, CustomerSSOClient, CustomerSSOGrant,
)
from pretix.multidomain.middlewares import CsrfViewMiddleware
from pretix.multidomain.urlreverse import build_absolute_uri
from pretix.presale.forms.customer_forms import AuthenticationForm
from pretix.presale.utils import customer_login, get_customer_auth_time

RESPONSE_TYPES_SUPPORTED = ("code", "id_token token", "id_token", "code id_token", "code id_token token", "code token")


class AuthorizeView(View):

    @method_decorator(csrf_exempt)
    @method_decorator(never_cache)
    @method_decorator(sensitive_post_parameters())
    def dispatch(self, request, *args, **kwargs):
        if not request.organizer.settings.customer_accounts or not request.organizer.settings.customer_accounts_native:
            raise Http404('Feature not enabled')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return self._process_auth_request(request, request.GET)

    def post(self, request, *args, **kwargs):

        try:
            CsrfViewMiddleware(lambda: None)._check_token(request)
        except:
            return redirect(request.path + '?' + request.POST.urlencode())
        return self._process_auth_request(request, request.GET)

    def _final_error(self, error, error_description):
        return HttpResponse(
            f'Error: {error_description} ({error})',
            status=400,
        )

    def _construct_redirect_uri(self, redirect_uri, response_mode, params):
        """
        Constructs a redirect URI by appending the given parameters in the specified response mode.

        Args:
            redirect_uri (str): The base redirect URI.
            response_mode (str): The response mode to use ('query' or 'fragment').
            params (dict): The parameters to append to the URI.

        Returns:
            str: The constructed redirect URI.
        """
        # Parse the redirect URI
        ru = urlparse(redirect_uri)

        # Parse the query and fragment components of the URI
        query_params = parse_qs(ru.query)
        fragment_params = parse_qs(ru.fragment)

        # Update the query or fragment parameters based on the response mode
        if response_mode == 'query':
            query_params.update(params)
        elif response_mode == 'fragment':
            fragment_params.update(params)

        # Encode the updated parameters
        query = urlencode(query_params, doseq=True)
        fragment = urlencode(fragment_params, doseq=True)

        # Construct and return the new URI with the updated parameters
        return urlunparse((ru.scheme, ru.netloc, ru.path, ru.params, query, fragment))

    def _redirect_error(self, error, error_description, redirect_uri, response_mode, state):
        qs = {'error': error, 'error_description': error_description}
        if state:
            qs['state'] = state
        return redirect(
            self._construct_redirect_uri(redirect_uri, response_mode, qs)
        )

    def _login_require(self, request: HttpRequest, client, scope, redirect_uri, response_type, response_mode, state,
                       nonce):
        """
        Handles the login requirement for a customer.

        Args:
            request (HttpRequest): The HTTP request object containing the customer's information.
            client (object): The client object for the login request.
            scope (str): The requested scope.
            redirect_uri (str): The redirect URI after successful login.
            response_type (str): The response type for the login request.
            response_mode (str): The response mode for the login request.
            state (str): The state parameter for maintaining state between request and callback.
            nonce (str): A unique string to associate the token with the authentication request.

        Returns:
            HttpResponse: The response to the login requirement.
        """
        form = AuthenticationForm(
            data=request.POST if "login-email" in request.POST else None,
            request=request,
            prefix="login"
        )

        if "login-email" in request.POST and form.is_valid():
            customer_login(request, form.get_customer())
            return self._success(
                client, scope, redirect_uri, response_type, response_mode, state, nonce, form.get_customer()
            )
        else:
            return render(request, 'pretixpresale/organizers/customer_login.html', {
                'providers': [],
                'form': form,
            })

    def _success(self, client, scope, redirect_uri, response_type, response_mode, state, nonce, customer):
        """
        Handles the successful authentication response.

        Args:
            client (object): The client object for the authentication request.
            scope (list): The requested scopes.
            redirect_uri (str): The redirect URI after successful login.
            response_type (str): The response type for the authentication request.
            response_mode (str): The response mode for the authentication request.
            state (str): The state parameter for maintaining state between request and callback.
            nonce (str): A unique string to associate the token with the authentication request.
            customer (object): The authenticated customer.

        Returns:
            HttpResponse: The redirect response with the appropriate query parameters.
        """
        response_types = response_type.split(' ')
        qs = {}
        id_token_kwargs = {}

        # Handle authorization code flow
        if 'code' in response_types:
            grant = client.grants.create(
                customer=customer,
                scope=' '.join(scope),
                redirect_uri=redirect_uri,
                code=get_random_string(64),
                expires=now() + timedelta(minutes=10),
                auth_time=get_customer_auth_time(self.request),
                nonce=nonce,
            )
            qs['code'] = grant.code
            id_token_kwargs['with_code'] = grant.code

        # Set token expiration time
        expires = now() + timedelta(hours=24)

        # Handle implicit flow (access token)
        if 'token' in response_types:
            token = client.access_tokens.create(
                customer=customer,
                token=get_random_string(128),
                expires=expires,
                scope=' '.join(scope),
            )
            qs['access_token'] = token.token
            qs['token_type'] = 'Bearer'
            qs['expires_in'] = int((token.expires - now()).total_seconds())
            id_token_kwargs['with_access_token'] = token.token

        # Handle ID token
        if 'id_token' in response_types:
            qs['id_token'] = generate_id_token(
                customer,
                client,
                get_customer_auth_time(self.request),
                nonce,
                ' '.join(scope),
                expires,
                scope_claims='token' not in response_types and 'code' not in response_types,
                **id_token_kwargs,
            )

        # Include state in the response if provided
        if state:
            qs['state'] = state

        # Construct the redirect URI with the query parameters
        redirect_uri = self._construct_redirect_uri(redirect_uri, response_mode, qs)
        response = redirect(redirect_uri)
        response['Cache-Control'] = 'no-store'
        response['Pragma'] = 'no-cache'

        return response

    def _process_auth_request(self, request, request_data):
        """
        Processes the authentication request based on the provided request data.

        Args:
            request (HttpRequest): The HTTP request object containing the customer's information.
            request_data (dict): A dictionary containing the authentication request parameters.

        Returns:
            HttpResponse: The appropriate response based on the authentication request processing.
        """
        response_mode = request_data.get("response_mode")
        client_id = request_data.get("client_id")
        state = request_data.get("state")
        nonce = request_data.get("nonce")
        max_age = request_data.get("max_age")
        prompt = request_data.get("prompt")
        response_type = request_data.get("response_type")
        scope = request_data.get("scope", "").split(" ")

        # Check if client_id is provided
        if not client_id:
            return self._final_error("invalid_request", "client_id missing")

        # Validate client_id
        try:
            client = self.request.organizer.sso_clients.get(is_active=True, client_id=client_id)
        except CustomerSSOClient.DoesNotExist:
            return self._final_error("unauthorized_client", "invalid client_id")

        # Validate redirect_uri
        redirect_uri = request_data.get("redirect_uri")
        if not redirect_uri or not client.allow_redirect_uri(redirect_uri):
            return self._final_error("invalid_request_uri", "invalid redirect_uri")

        # Validate response_type
        if response_type not in RESPONSE_TYPES_SUPPORTED:
            return self._final_error("unsupported_response_type", "response_type unsupported")

        # Validate response_mode
        if response_type != "code" and response_mode == "query":
            return self._final_error("invalid_request",
                                     "response_mode query must not be used with implicit or hybrid flow")
        elif not response_mode:
            response_mode = "query" if response_type == "code" else "fragment"
        elif response_mode not in ("query", "fragment"):
            return self._final_error("invalid_request", "invalid response_mode")

        # Check if request parameter is present
        if "request" in request_data:
            return self._redirect_error("request_not_supported", "request_not_supported", redirect_uri, response_mode,
                                        state)

        # Validate nonce for implicit or hybrid flow
        if response_type not in ("code", "code token") and not nonce:
            return self._redirect_error("invalid_request", "nonce is required in implicit or hybrid flow", redirect_uri,
                                        response_mode, state)

        # Ensure 'openid' scope is requested
        if "openid" not in scope:
            return self._redirect_error("invalid_scope", "scope 'openid' must be requested", redirect_uri,
                                        response_mode, state)

        # Check if id_token_hint is provided
        if "id_token_hint" in request_data:
            self._redirect_error("invalid_request", "id_token_hint currently not supported by this server",
                                 redirect_uri, response_mode, state)

        # Check for valid session
        has_valid_session = bool(request.customer)
        if has_valid_session and max_age:
            try:
                has_valid_session = int(time.time() - get_customer_auth_time(request)) < int(max_age)
            except ValueError:
                self._redirect_error("invalid_request", "invalid max_age value", redirect_uri, response_mode, state)

        if not has_valid_session and prompt and prompt == "none":
            return self._redirect_error("interaction_required", "user is not logged in but no prompt is allowed",
                                        redirect_uri, response_mode, state)
        elif prompt in ("select_account", "login"):
            has_valid_session = False

        # Process based on session validity
        if has_valid_session:
            return self._success(client, scope, redirect_uri, response_type, response_mode, state, nonce,
                                 request.customer)
        else:
            return self._login_require(request, client, scope, redirect_uri, response_type, response_mode, state, nonce)


class TokenView(View):
    @method_decorator(csrf_exempt)
    @method_decorator(never_cache)
    @method_decorator(sensitive_post_parameters())
    def dispatch(self, request, *args, **kwargs):
        """
        Handles the dispatching of the request and checks if the feature is enabled.
        """
        if not request.organizer.settings.customer_accounts or not request.organizer.settings.customer_accounts_native:
            raise Http404('Feature not enabled')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handles the POST request and processes the token request.
        """
        self.client = self._validate_client(request)
        if not self.client:
            return JsonResponse({
                "error": "invalid_client",
                "error_description": "Client validation failed"
            }, status=400)

        grant_type = request.POST.get("grant_type")
        if grant_type == "authorization_code":
            return self._handle_authorization_code(request)
        else:
            return JsonResponse({
                "error": "unsupported_grant_type"
            }, status=400)

    def _validate_client(self, request):
        """
        Validates the client credentials from the request.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            CustomerSSOClient: The validated client or None if validation fails.
        """
        auth_header = request.headers.get('Authorization')
        if auth_header:
            encoded_credentials = auth_header.split(' ')[1]
            decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8").split(':')
            client_id = decoded_credentials[0]
            client_secret = decoded_credentials[1]
            try:
                client = request.organizer.sso_clients.get(client_id=client_id, is_active=True)
            except CustomerSSOClient.DoesNotExist:
                return None
            if not client.check_client_secret(client_secret):
                return None
        elif request.POST.get("client_id"):
            try:
                client = request.organizer.sso_clients.get(client_id=request.POST["client_id"], is_active=True)
            except CustomerSSOClient.DoesNotExist:
                return None
            if "client_secret" in request.POST:
                if not client.check_client_secret(request.POST.get("client_secret")):
                    return None
            elif client.client_type != CustomerSSOClient.CLIENT_PUBLIC:
                return None
        else:
            return None
        return client

    def _handle_authorization_code(self, request):
        """
        Handles the authorization code grant type.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            JsonResponse: The JSON response with the access token or error.
        """
        code = request.POST.get("code")
        redirect_uri = request.POST.get("redirect_uri")
        if not code:
            return JsonResponse({
                "error": "invalid_grant",
            }, status=400)

        try:
            grant = self.client.grants.get(code=code, expires__gt=now())
        except CustomerSSOGrant.DoesNotExist:
            CustomerSSOAccessToken.objects.filter(
                client=self.client,
                from_code=code
            ).update(expires=now() - timedelta(seconds=1))
            return JsonResponse({
                "error": "invalid_grant",
                "error_description": "Unknown or expired authorization code"
            }, status=400)

        if grant.redirect_uri != redirect_uri:
            return JsonResponse({
                "error": "invalid_grant",
                "error_description": "Mismatch of redirect_uri"
            }, status=400)

        with transaction.atomic():
            token = self.client.access_tokens.create(
                customer=grant.customer,
                token=get_random_string(128),
                expires=now() + timedelta(hours=24),
                scope=grant.scope,
                from_code=code,
            )
            grant.delete()

        return JsonResponse({
            "access_token": token.token,
            "token_type": "Bearer",
            "expires_in": int((token.expires - now()).total_seconds()),
            "id_token": generate_id_token(grant.customer, self.client, grant.auth_time, grant.nonce, grant.scope,
                                          token.expires)
        }, headers={
            'Cache-Control': 'no-store',
            'Pragma': 'no-cache',
        })


class UserInfoView(View):
    @method_decorator(csrf_exempt)
    @method_decorator(never_cache)
    @method_decorator(sensitive_post_parameters())
    def dispatch(self, request, *args, **kwargs):
        """
        Handles the dispatching of the request and checks if the feature is enabled.
        """
        if not request.organizer.settings.customer_accounts or not request.organizer.settings.customer_accounts_native:
            raise Http404('Feature not enabled')

        token = self._get_token_from_request(request)
        if not token:
            return HttpResponse(status=401, headers={
                'WWW-Authenticate': 'Bearer realm="example"',
                'Access-Control-Allow-Origin': '*',
            })

        try:
            access_token = CustomerSSOAccessToken.objects.get(
                token=token, expires__gt=now(), client__organizer=self.request.organizer,
            )
        except CustomerSSOAccessToken.DoesNotExist:
            return JsonResponse({
                "error": "invalid_token",
                "error_description": "Unknown access token"
            }, status=401, headers={
                'WWW-Authenticate': 'error="invalid_token"&error_description="Unknown access token"',
                'Access-Control-Allow-Origin': '*',
            })
        else:
            self.customer = access_token.customer
            self.access_token = access_token

        response = super().dispatch(request, *args, **kwargs)
        response['Access-Control-Allow-Origin'] = '*'
        return response

    def _get_token_from_request(self, request):
        """
        Extracts the token from the request headers or POST data.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            str: The extracted token or None if not found.
        """
        auth_header = request.headers.get('Authorization')
        if auth_header:
            method, token = auth_header.split(' ', 1)
            if method != 'Bearer':
                return None
            return token
        elif request.method == "POST" and "access_token" in request.POST:
            return request.POST.get("access_token")
        return None

    def post(self, request, *args, **kwargs):
        """
        Handles the POST request and returns the JSON response with the customer claims.
        """
        return self._handle(request)

    def get(self, request, *args, **kwargs):
        """
        Handles the GET request and returns the JSON response with the customer claims.
        """
        return self._handle(request)

    def _handle(self, request):
        """
        Processes the request and returns the JSON response with the customer claims.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            JsonResponse: The JSON response with the customer claims.
        """
        return JsonResponse(
            customer_claims(self.customer, self.access_token.client.evaluated_scope(self.access_token.scope))
        )


class KeysView(View):
    def dispatch(self, request, *args, **kwargs):
        """
        Handles the dispatching of the request and checks if the feature is enabled.
        """
        if not request.organizer.settings.customer_accounts or not request.organizer.settings.customer_accounts_native:
            raise Http404('Feature not enabled')
        response = super().dispatch(request, *args, **kwargs)
        response['Access-Control-Allow-Origin'] = '*'
        return response

    def _encode_int(self, i):
        """
        Encodes an integer to a URL-safe base64 string.
        """
        hexi = hex(i)[2:]
        return base64.urlsafe_b64encode(unhexlify((len(hexi) % 2) * '0' + hexi))

    def _generate_keys(self, organizer):
        """
        Generates the public key and its metadata.
        """
        privkey, pubkey = _get_or_create_server_keypair(organizer)
        kid = hashlib.sha256(pubkey.encode()).hexdigest()[:16]
        pubkey = RSA.import_key(pubkey)
        return {
            'kty': 'RSA',
            'alg': 'RS256',
            'kid': kid,
            'use': 'sig',
            'e': self._encode_int(pubkey.e).decode().rstrip("="),
            'n': self._encode_int(pubkey.n).decode().rstrip("="),
        }

    def get(self, request, *args, **kwargs):
        """
        Handles the GET request and returns the JSON response with the keys.
        """
        keys = self._generate_keys(request.organizer)
        return JsonResponse({'keys': [keys]})


class WellKnownConfigurationView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.organizer.settings.customer_accounts or not request.organizer.settings.customer_accounts_native:
            raise Http404('Feature not enabled')
        response = super().dispatch(request, *args, **kwargs)
        response['Access-Control-Allow-Origin'] = '*'
        return response

    def get(self, request, *args, **kwargs):
        def build_configuration():
            return {
                'issuer': build_absolute_uri(request.organizer, 'presale:organizer.index').rstrip('/'),
                'authorization_endpoint': build_absolute_uri(
                    request.organizer, 'presale:organizer.oauth2.v1.authorize'
                ),
                'token_endpoint': build_absolute_uri(
                    request.organizer, 'presale:organizer.oauth2.v1.token'
                ),
                'userinfo_endpoint': build_absolute_uri(
                    request.organizer, 'presale:organizer.oauth2.v1.userinfo'
                ),
                'jwks_uri': build_absolute_uri(
                    request.organizer, 'presale:organizer.oauth2.v1.jwks'
                ),
                'scopes_supported': [k for k, v in CustomerSSOClient.SCOPE_CHOICES],
                'token_endpoint_auth_methods_supported': [
                    'client_secret_post', 'client_secret_basic'
                ],
                'response_types_supported': RESPONSE_TYPES_SUPPORTED,
                'response_modes_supported': ['query', 'fragment'],
                'request_parameter_supported': False,
                'grant_types_supported': ['authorization_code', 'implicit'],
                'subject_types_supported': ['public'],
                'id_token_signing_alg_values_supported': ['RS256'],
                'claims_supported': [
                    'iss',
                    'aud',
                    'exp',
                    'iat',
                    'auth_time',
                    'nonce',
                    'c_hash',
                    'at_hash',
                    'sub',
                    'locale',
                    'name',
                    'given_name',
                    'family_name',
                    'middle_name',
                    'nickname',
                    'email',
                    'email_verified',
                    'phone_number',
                ],
                'request_uri_parameter_supported': False,
            }

        configuration = build_configuration()
        return JsonResponse(configuration)
