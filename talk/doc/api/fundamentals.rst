API principles
==============

This page describes basic concepts and definition that you need to know to
interact with the pretalx REST API, such as authentication, pagination and
similar definitions.

.. _`authentication`:

Authentication
--------------

The authenticated use of the API is only available to organisers, including reviewers.
Some endpoints are available to non-authenticated users, like e.g. the schedule
end point – however, authenticated use of the same endpoints will often include
additional data.

You can see, create and disable your API tokens in the organiser frontend at
``/orga/me``. API tokens are always scoped to specific endpoints and events.
While pretalx comes with shortcuts to create tokens with all read or all
read-write permissions, we highly recommend that you limit your tokens to the
endpoints and permissions that they actually need, to reduce the security
impact of accidentally revealing your token to others.

Include your API token with every request to the API in the ``Authorization``
header like this:

.. sourcecode:: http
   :emphasize-lines: 3

   GET /api/events/ HTTP/1.1
   Host: pretalx.com
   Authorization: Token e1l6gq2ye72thbwkacj7jbri7a7tvxe614ojv8ybureain92ocub46t5gab5966k

If you were using the pretalx API before v2025.1.0, when the new API tokens
were introduced, your old API tokens will continue working. They will be automatically
scoped to use the legacy API for as long as it continues working (see :ref:`api-versioning`).

API tokens with an expiry date in the past will be periodically deleted.

.. _`api-versioning`:

Versioning
----------

As pretalx is under active development, and we have to make changes to the API
for both new and existing features, the pretalx API exists in multiple
versions. Your API version is saved **the first time you use an API token**.
All subsequent requests with this token will use the same version (for as long
as it is available), so that you don’t have to worry about API changes after
pretalx updates, for example.

The pretalx API version *can* change in a new release, but does not *have* to
change: sometimes, a pretalx release will not contain any API changes, and it
would be needlessly annoying to users to still increment the API version. So,
while pretalx uses a calendar-based API versioning scheme, and will continue to
note relevant API changes in the :ref:`changelog`, there is also a separate
:ref:`api-changelog` listing API versions to help you update your tokens.

The following changes do **not** lead to a new API version release, so your
client should be able to deal with them gracefully:

- Adding new fields to existing resources
- Changing the order of fields within an object
- Adding new endpoints to the API (these will be unavailable to existing tokens, as tokens are limited to the endpoints selected at creation)
- Making an existing field expandable (see :ref:`api-expansion`)
- Supporting new optional query parameters
- Changing the search range of the ``?q=`` search query parameter in an endpoint
- Changing the default ordering of a list page
- Changing the length, format or content of opaque strings such as object IDs or error messages
- Changing the default pagination size
- Introducing or changing API rate limits (be prepared to handle HTTP ``429 Too Many Requests`` responses with a ``Retry-After`` header)

When a pretalx release contains a new API version, the previous API version
will **still be available** in that release. It will show up as “deprecated”
in your API token list, and you can update an existing API token to use the
new version there. In order to test things without updating your token, you
can also temporarily override the API version used in a request with the
``Pretalx-Version`` header like this:

.. sourcecode:: http
   :emphasize-lines: 3

   GET /api/events/ HTTP/1.1
   Host: pretalx.com
   Pretalx-Version: v1
   Authorization: Token e1l6gq2ye72thbwkacj7jbri7a7tvxe614ojv8ybureain92ocub46t5gab5966k

Deprecated API versions will be removed in the next pretalx release by default,
though we may extend support for versions to a second release: On the one hand,
we want to reduce our maintenance burden by not having to maintain more than
two API versions at all times. On the other hand, users of pretalx often only
use the API once per year for their yearly conference, and depending on the
amount of changes we introduce, that could result in always having to upgrade
to a new API version.

This is what an example timeline would look like for API version deprecation:

v2025.1.0
    API v1 is introduced
v2025.2.0
    API remains at v1, with a new endpoint added, but no breaking changes.
v2026.1.0
    API v2 is introduced changing the format of the ``speakers`` attribute of the ``/submissions/`` endpoint. API v1 is marked as deprecated, but continues working. Existing tokens use API v1 per default, and can be upgraded to v2.
v2026.2.0
    The deprecated API v1 is removed. Tokens still using v1 are no longer working, and have to be upgraded to v2.


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
datetime              String in ISO 8601 format    ``"2017-12-27T10:00:00Z"``
                      with time zone (often UTC,   ``"2017-12-27T10:00:00.596934Z"``,
                      or the event timezone)       ``"2017-12-27T10:00:00+02:00"``
date                  String in ISO 8601 format    ``2017-12-27``
multi-language string Object of strings            ``{"en": "red", "de": "rot"}``
===================== ============================ ===================================

Multi-language strings
^^^^^^^^^^^^^^^^^^^^^^

All multi-language strings can be converted into a simple string by making a
request with the ``lang`` query parameter, e.g. ``?lang=en``. If the language
is available within the event context, the strings will be coerced to be in the
chosen language, falling back on other available strings if the string is empty
in the selected language.

.. _`api-expansion`:

Expanding linked resources
--------------------------

A lot of data is interlinked in the pretalx API. For example, a ``submission``
endpoint resource will contain references to a track, a submission type,
several tags and speakers, slots, which belong to a schedule and take place in
a room, and so on.

By default, these references are returned by ID. This keeps the API response to
a reasonable size and cost, especially on list view endpoints. However, in the
case of the submission example above, this would require you to make at least
six additional API calls to resolve all the referenced resources.

In most endpoints, you can instead get all information in a single request with
the help of the ``expand`` query parameter. The fields available for expansion
are documented in the API endpoints documentation (:ref:`api-endpoints`).

You can expand multiple, and even nested parameters by separating them with
a comma: ``?expand=speakers,track,submission_type,slots.room``.
Expansions can go multiple levels deep, e.g. ``?expand=speakers.answers.question``.

Please note that expansions on large endpoints, like e.g. the schedule
endpoint, place a noticeable note on the pretalx server. Please use expansion
responsibly, and ideally cache results for future use. The pretalx API may
implement rate limits based on a user’s frequency or cost of API requests
without prior warning.


Pagination
----------

The API will paginate most lists of objects. The response will take the form
of:

.. sourcecode:: json

    {
        "count": 117,
        "next": "https://pretalx.yourdomain.com/api/v1/organisers/?page=2",
        "previous": null,
        "results": []
    }

As you can see, the response contains the total number of results in the field
``count``.  The fields ``next`` and ``previous`` contain links to the next and
previous page of results, respectively, or ``null`` if there is no such page.
You can also use the special ``?page=last`` parameter to retrieve the last
page.

By default, the page size (that is, the length of the ``results`` field) is 50.
You can decrease the page size with the ``page_size`` parameter, but for
performance reasons, you cannot increase it past 50.

File uploads
------------

In some places, the API supports working with files, for example when uploading
a speaker avatar or a submission resource. In this case, you will first need to
make a separate request to the file upload endpoint:

.. sourcecode:: http

   POST /api/upload/ HTTP/1.1
   Host: pretalx.com
   Authorization: Token e1l6gq2ye72thbwkacj7jbri7a7tvxe614ojv8ybureain92ocub46t5gab5966k
   Content-Type: image/png
   Content-Disposition: attachment; filename="logo.png"
   Content-Length: 1234

   <raw file content>

Note that the ``Content-Type`` and ``Content-Disposition`` headers are required.
If the upload was successful, you will receive a JSON response with the ID of the file.
You can find details in the endpoint documentation (:ref:`api-endpoints`).

You can then use this file ID in the request you want to use it in. File IDs
are valid for 24 hours, and can only be used by the user who uploaded them.


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

Searching and filtering
-----------------------

Most list endpoints allow a filtering of the results using query parameters.
Filters can be IDs (numeric or strings) or booleans when filtering by a flag – in
this case, you should pass booleans as the string values ``true`` and
``false``.

Most list endpoints support searching select fields of the resources.  This
search will be case insensitive unless noted otherwise, and you can access it
via the ``?q=`` query parameter.


Best Practices
--------------

When you use the pretalx API, we’d like to ask you to keep the following points
in mind:

**Be respectful of pretalx resources**: Keep your API use to a reasonable load.
Apply time-outs between API calls, keep your requests simple when possible by
not requesting deeply nested data when not needed, and cache data that does not
change. Try to avoid receiving ``429 Too Many Requests`` responses. If you
receive a ``500 Internal Server Error`` response, please notify the server
operator or open a bug report.

**Secure your API tokens**: Even when limiting your API token scope, an API
token will by definition grant access to non-public data. Make sure that your
token is secured adequately, so that private information like speaker email
addresses or review contents do not become public. Do not your API token on
public websites.


Limitations
-----------

There are some known limitations to the pretalx API. Some of these are by design,
like the fact that authenticated API access is only permitted to organisers and
reviewers: While this limitation *could* be removed, it would place an enormous
additional maintenance burden on making sure that all access permissions are
handled correctly for authenticated non-organiser users.

In a similar vein, users with *only* reviewer permissions for a given event
will not be able to use the API while anonymised reviews are active. This is
because during anonymous reviews, various information is obscured from
reviewers: not just speaker names, but also some questions and answers,
abstracts, and other fields. Making sure that these fields will be hidden from
reviewers in all views, including expanded fields several layers deep, would be
too easy to get wrong, so instead, we’re disabling API access for that time
entirely.

.. _CSRF policies: https://docs.djangoproject.com/en/stable/howto/csrf/#using-csrf-protection-with-ajax
