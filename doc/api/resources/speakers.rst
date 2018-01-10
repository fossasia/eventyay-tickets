Speakers
=========

Resource description
--------------------

The submission resource contains the following public fields:

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
code                                  string                     A unique, alphanumeric identifier, also used in URLs
name                                  string                     The speaker's public name
biography                             string                     The speaker's self-submitted biography, markdown-formatted text.
submissions                           list                       A list of submission codes, e.g. ``["ABCDEF", "GHIJKL"]``
===================================== ========================== =======================================================

Endpoints
---------

.. http:get:: /api/events/{event}/speakers/

   Returns a list of all speakers the authenticated user/token has access to, or
   all confirmed, publicly scheduled speakers for unauthenticated users.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/speakers/ HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      {
        "count": 1,
        "next": null,
        "previous": null,
        "results": [
          {
            "code": "ABCDE",
            "name": "Jane",
            "biography": "A good speaker",
            "submissions": ["DEFAB"]
            }
          }
        ]
      }

   :param event: The ``slug`` field of the event to fetch
   :query page: The page number in case of a multi-page result set, default is 1
   :query q: Search through submissions by speaker name

.. http:get:: /api/events/(event)/speakers/{code}/

   Returns information on one event, identified by its slug.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/submissions/ABCDE HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      {
        "code": "ABCDE",
        "name": "Jane",
        "biography": "A good speaker",
        "submissions": ["DEFAB"]
      }

   :param event: The ``slug`` field of the event to fetch
   :param code: The ``code`` field of the speaker to fetch
   :statuscode 200: no error
   :statuscode 401: Authentication failure
   :statuscode 403: The requested event does not exist **or** you have no permission to view it.
