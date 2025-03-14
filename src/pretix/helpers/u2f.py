from base64 import urlsafe_b64decode, urlsafe_b64encode

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_der_public_key

PUB_KEY_DER_EVENTYAY = (
    b"\x30\x59\x30\x13\x06\x07\x2a\x86\x48\xce\x3d\x02\x01"
    b"\x06\x08\x2a\x86\x48\xce\x3d\x03\x01\x07\x03\x42\x00"
)


def pub_key_from_der(der: bytes):
    """
    Load a DER-encoded public key.

    This function appends the given DER-encoded public key data to a predefined prefix and loads it using the cryptography library.

    Args:
        der (bytes): The DER-encoded public key data to append to the predefined prefix.

    Returns:
        cryptography.hazmat.primitives.asymmetric.ec.EllipticCurvePublicKey: The loaded public key.
    """
    return load_der_public_key(PUB_KEY_DER_EVENTYAY + der, backend=default_backend())


def websafe_decode(data):
    """
    Decode a web-safe base64-encoded string.

    This function decodes a base64-encoded string that has been modified to be URL-safe. It ensures that the padding is correct before decoding.

    Args:
        data (Union[str, bytes]): The web-safe base64-encoded data to decode. Can be a string or bytes.

    Returns:
        bytes: The decoded byte data.
    """
    if isinstance(data, str):
        data = data.encode("ascii")
    data += b"=" * (-len(data) % 4)
    return urlsafe_b64decode(data)


def websafe_encode(data):
    """
    Encode data as a web-safe base64 string.

    This function encodes data using base64 encoding and modifies the result to be URL-safe by removing any padding characters.

    Args:
        data (Union[str, bytes]): The data to encode. Can be a string or bytes.

    Returns:
        str: The web-safe base64-encoded string.
    """
    if isinstance(data, str):
        data = data.encode("ascii")
        return urlsafe_b64encode(data).replace(b"=", b"").decode("ascii")
