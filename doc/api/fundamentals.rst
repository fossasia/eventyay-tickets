Basic concepts
==============

This page describes basic concepts and definition that you need to know to
interact with the pretalx REST API, such as authentication, pagination and
similar definitions.

.. _`rest-auth`:

Obtaining an API token
----------------------

To authenticate your API requests, you need an API token. You can view your API
token in the organiser frontend at ``/orga/me``, or you can direct a POST
request containing your ``username`` and ``password`` to ``/api/auth`` – this
endpoint will respond with ``{"token": "abcd…"}``.


Authentication
--------------

You need to include the API token with every request to the API in the
``Authorization`` header like the following:

.. sourcecode:: http
   :emphasize-lines: 2

   GET /api/v1/organisers/ HTTP/1.1
   Authorization: Token e1l6gq2ye72thbwkacj7jbri7a7tvxe614ojv8ybureain92ocub46t5gab5966k

You can use the ``/api/me`` endpoint afterwards to see who you are logged in as.
It returns an object with your ``name``, ``email``, ``locale`` and ``timezone``.

.. note:: The API also supports authentication via browser sessions,
          the same way that you authenticate with pretalx when using the
          browser interface.  Using this authentication is *not*
          officially supported for use by third-party clients and we may change
          or remove it at any time. If you want to use session authentication,
          be sure to follow Django's `CSRF policies`_.

Compatibility
-------------

The API is under heavy development – please don't rely on its format to remain
the same. We will document changes in our :ref:`changelog` as always.

We may always add fields or endpoints, or support new methods or query
parameters on existing endpoints without further notice, so please make sure
your client can deal with this.

We will give prior notice in our :ref:`changelog` before removing endpoints,
API methods, fields, or before changing response fields, or requiring new input
fields or types.

Pagination
----------

The API will paginate most lists of objects. The response will take the form
of:

.. sourcecode:: javascript

    {
        "count": 117,
        "next": "https://pretalx.yourdomain.com/api/v1/organisers/?limit=20&offset=40",
        "previous": null,
        "results": […],
    }

As you can see, the response contains the total number of results in the field
``count``.  The fields ``next`` and ``previous`` contain links to the next and
previous page of results, respectively, or ``null`` if there is no such page.
You can use those URLs to retrieve the respective page.

The field ``results`` contains a list of objects representing the first
results. For most objects, every page contains 25 results.

Errors
------

The API returns error responses (of type 400-499) in one of the following
forms, depending on the error. General errors look like:

.. sourcecode:: http

   HTTP/1.1 405 Method Not Allowed
   Content-Type: application/json
   Content-Length: 42

   {"detail": "Method 'DELETE' not allowed."}

Field specific input errors include the name of the offending fields as keys in the response:

.. sourcecode:: http

   HTTP/1.1 400 Bad Request
   Content-Type: application/json
   Content-Length: 94

   {"amount": ["Please submit a valid integer."], "description": ["This field may not be blank."]}


Data types
----------

The API returns all structured responses in JSON format using standard JSON
data types such as integers, floating point numbers, strings, lists, objects
and booleans. Most fields can be ``null`` as well.

The following table shows some data types that have no native JSON
representation and how we serialise them to JSON.

===================== ============================ ===================================
Internal type         JSON representation          Examples
===================== ============================ ===================================
Datetime              String in ISO 8601 format    ``"2017-12-27T10:00:00Z"``
                      with time zone (often UTC)   ``"2017-12-27T10:00:00.596934Z"``,
                                                   ``"2017-12-27T10:00:00+02:00"``
Date                  String in ISO 8601 format    ``2017-12-27``
Multi-lingual string  Object of strings            ``{"en": "red", "de": "rot"}``
===================== ============================ ===================================

Query parameters
----------------

Most list endpoints allow a filtering of the results using query parameters. In
this case, you should pass booleans as the string values ``true`` and
``false``.

Most list endpoints support searching select fields of the resources.  This
search will be case insensitive unless noted otherwise, and you can access it
via the ``?q=`` query parameter.

If you see the ``o`` parameter on a resource, you can use it to sort the result
set by one of the allowed fields. Prepend a ``-`` to the field name to reverse
the sort order.

.. _CSRF policies: https://docs.djangoproject.com/en/1.11/ref/csrf/#ajax
