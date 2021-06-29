Iframe Guest API
================

Venueless rooms can contain arbitrary iframes. This is often used for embedding third-party applications or static
content. Venueless exposes a few ways for those iframes to interact with the main application if desired.

URL parameters
--------------

The target URL of the iframe may contain parameters that will be expanded by venueless. For example, if you want
to prefill the name of the user in a third-party application, you could use::

    https://other-application.com/embed?name={display_name}

Currently, the following parameters are supported:

* ``{display_name}`` – The user's public display name
* ``{id}`` – The user's unique ID in veneuless (UUID format)

.. warning::

   **You may under no circumstances use this for authentication purposes.** All supported parameters including the user
   ID are **public information** and if you'd use them to authenticate users to a third-party service, everyone could
   impersonate them easily.
