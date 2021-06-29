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


Routing
-------

You can route the user to a different location in venueless by sending a JavaScript message to the main application.
An example that moves the user to a room with a specific ID would look like this::

    window.parent.postMessage(
        {
            action: 'router.push',
            location: {
                name: 'room',
                params: {roomId: 'c1efbc6f-4cb3-4be3-9b8a-8ab5cffec6cb'}
            }
        },
        '*'
    )

The ``location`` needs to be a valid location as defined by the `Vue Router API`_.

.. note::

   The exact naming of all routes inside Venueless as well as the exact version of Vue Router we're using are not
   considered stable APIs and might change in the future. Simple routes to a specific room such as the one in the
   example above should be safe for the future.

.. _Vue Router API: https://router.vuejs.org/guide/essentials/navigation.html#router-push-location-oncomplete-onabort
