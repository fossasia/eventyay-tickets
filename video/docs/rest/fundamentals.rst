Basic concepts
==============

This page describes basic concepts and definition that you need to know to interact with venueless' public REST API,
such as authentication, pagination and similar definitions.

.. _`rest-auth`:

Authentication
--------------

To access the API, you need to present valid authentication credentials. These credentials currently take the form
of an JWT token that is issued by a valid identity provider for a given world. The API currently does not allow
any access across the scope of one world.

You can send your authorization token in the ``Authorization`` Header::

    Authorization: Bearer myverysecretjwttoken

Accessing the API requires that your JWT token is granted at least the ``world.api`` permission.

Pagination
----------

Most lists of objects returned by venueless' API will be paginated. The response will take the form of:

.. sourcecode:: javascript

    {
        "count": 117,
        "next": "https://world.venueless.org/api/v1/organizers/?page=2",
        "previous": null,
        "results": […],
    }

As you can see, the response contains the total number of results in the field ``count``.
The fields ``next`` and ``previous`` contain links to the next and previous page of results,
respectively, or ``null`` if there is no such page. You can use those URLs to retrieve the
respective page.

The field ``results`` contains a list of objects representing the first results. For most
objects, every page contains 50 results.

Errors
------

Error responses (of type 400-499) are returned in one of the following forms, depending on
the type of error. General errors look like:

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

   {"amount": ["A valid integer is required."], "description": ["This field may not be blank."]}

Data types
----------

All structured API responses are returned in JSON format using standard JSON data types such
as integers, floating point numbers, strings, lists, objects and booleans. Most fields can
be ``null`` as well.

The following table shows some data types that have no native JSON representation and how
we serialize them to JSON.

===================== ============================ ===================================
Internal type         JSON representation          Examples
===================== ============================ ===================================
Datetime              String in ISO 8601 format    ``"2017-12-27T10:00:00Z"``
                      with timezone (normally UTC) ``"2017-12-27T10:00:00.596934Z"``,
                                                   ``"2017-12-27T10:00:00+02:00"``
Date                  String in ISO 8601 format    ``2017-12-27``
===================== ============================ ===================================

Query parameters
^^^^^^^^^^^^^^^^

Most list endpoints allow a filtering of the results using query parameters. In this case, booleans should be passed
as the string values ``true`` and ``false``.

If the ``ordering`` parameter is documented for a resource, you can use it to sort the result set by one of the allowed
fields. Prepend a ``-`` to the field name to reverse the sort order.
