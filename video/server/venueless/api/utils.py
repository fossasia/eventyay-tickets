from urllib.parse import urlparse


def get_protocol(url):
    parsed = urlparse(url)
    protocol = parsed.scheme
    return protocol.lower()
