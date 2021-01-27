Authentication
==============

Authentication to venueless is done exclusively through `JSON Web Tokens`_ (JWT). Unless the venueless world allows
public access, it can only be joined with a valid JWT.

When the user first joins, this token needs to be passed by URL like this::

    https://demo.venueless.events/#token=ey...

Venueless will then store the token in the local storage of the user's browser for subsequent access. The token needs
to use the ``HS256`` signature scheme and include at least the following keys:

``iss``
    The issuer identifier for the token, needs to exactly match the configuration of the venueless world. The string
    is arbitrary, but defaults to ``"any"`` in venueless' default configuration.

``aud``
    The audience identifier for the token, needs to exactly match the configuration of the venueless world. The string
    is arbitrary, but defaults to ``"venueless"`` in venueless' default configuration.

``exp``
    The expiration date of the token (UNIX timestamp).

``iat``
    The creation date of the token (UNIX timestamp).

``uid``
    An arbitrary string of at most 200 characters that uniquely identifies the user. This needs to be different for each
    user (otherwise all users log in to the same account), and it needs to stay the same for the same person (otherwise
    a new venueless user is created every time the person joins). If you do not have user IDs in your system, you could
    e.g. use a salted hash of email addresses or something similar.

``traits``
    A one-dimensional array of arbitrary strings of at most 200 characters. Each string is considered one "trait"
    assigned to the person. Traits should not include spaces, commas or ``|`` characters. These traits are later used
    to map the user to a set of permissions inside venueless. For example, the ticketing system pretix assignes traits
    of the form ``pretix-event-1234`` with the ID of the event, ``pretix-item-5678`` with the ID of the product that has
    been bought, and so on. If your system has a concept like "user groups" or "roles", this would be the place to
    encode them.

Optionally, you can also pass the following fields:

``profile``
    A JSON dictionary containing additional information that is used to prefill the user profile. Currently, the two
    keys ``display_name`` and ``fields`` are allowed, where ``display_name`` is a string and ``fields`` is a mapping
    of venueless field IDs to values::

        {
            "display_name": "John Doe",
            "fields": {
                "e5b06da1-ca18-4204-8b68-769ff86220a9": "@venueless"
            }
        }



.. _JSON Web Tokens: https://en.wikipedia.org/wiki/JSON_Web_Token
