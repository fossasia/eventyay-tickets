from datetime import datetime, timedelta

import jwt
from django.conf import settings


def generate_sso_token(user):
    """
    Generate a JWT token for the user.
    @param user: User obj
    @return: jwt token
    """
    if user and user.is_authenticated:
        jwt_payload = {
            'email': user.email,
            'name': user.get_full_name(),
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'locale': user.locale,
            'timezone': user.timezone,
            'exp': datetime.utcnow() + timedelta(hours=1),  # Token expiration
            'iat': datetime.utcnow(),
        }
        jwt_token = jwt.encode(jwt_payload, settings.SECRET_KEY, algorithm='HS256')
        return jwt_token
    return None


def generate_customer_sso_token(customer):
    """
    Generate a JWT token for the user.
    @param customer: User obj
    @return: jwt token
    """
    if customer:
        jwt_payload = {
            'email': customer.email,
            'name': customer.name,
            'customer_identifier': customer.identifier,
            'is_active': customer.is_active,
            'locale': customer.locale,
            'exp': datetime.utcnow() + timedelta(hours=1),  # Token expiration
            'iat': datetime.utcnow(),
        }
        jwt_token = jwt.encode(jwt_payload, settings.SECRET_KEY, algorithm='HS256')
        return jwt_token
    return None
