Speakers
=========

Resource description
--------------------

The speaker resource contains the following public fields:

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
code                                  string                     A unique, alphanumeric identifier, also used in URLs
name                                  string                     The speaker's public name
biography                             string                     The speaker's self-submitted biography, markdown-formatted text.
submissions                           list                       A list of submission codes, e.g. ``["ABCDEF", "GHIJKL"]``
avatar                                string                     The speaker avatar URL
email                                 string                     The speaker's email address. Available if the requesting user has organiser privileges.
availabilities                        list                       A list of availability objects, containing the fields ``id``, ``start``, ``end``, and ``allDay`` for each availability object. Available if the requesting user has organiser privileges.
answers                               list                       The question answers given by the speakers. Available if the requesting user has organiser permissions, and if the ``questions`` query parameter is passed.
===================================== ========================== =======================================================

.. versionadded:: 1.1.0
   The ``availabilities`` field for organisers was added in pretalx v1.1.0.

.. versionadded:: 3.0.0
   The ``answers`` field for organisers was added in pretalx v3.0.0. You need to pass the ``questions`` query parameter to populate this field. You can set it to ``all`` to retrieve answers to all speaker questions.

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
            "submissions": ["DEFAB"],
            "avatar": "https://example.org/media/avatar.png",
            "availabilities": [
              {
                "id": 1,
                "start": "2019-07-24T04:00:00Z",
                "end": "2019-07-25T04:00:00Z",
                "allDay": false
              }
            ]
          }
        ]
      }

   :param event: The ``slug`` field of the event to fetch
   :query page: The page number in case of a multi-page result set, default is 1
   :query q: Search through speakers by name
   :query questions: Pass a comma separated list of question IDs to load, or the string 'all' to return all answers.

.. http:get:: /api/events/(event)/speakers/{code}/

   Returns information on one speaker, identified by their slug.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/speakers/ABCDE HTTP/1.1
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
        "submissions": ["DEFAB"],
        "avatar": "https://example.org/media/avatar.png",
        {
          "id": 1,
          "start": "2019-07-24T04:00:00Z",
          "end": "2019-07-25T04:00:00Z",
          "allDay": false
        }
      }

   :param event: The ``slug`` field of the event to fetch
   :param code: The ``code`` field of the speaker to fetch
   :query questions: Pass a comma separated list of question IDs to load, or the string 'all' to return all answers.
   :statuscode 200: no error
   :statuscode 401: Authentication failure
   :statuscode 403: The requested event does not exist **or** you have no permission to view it.
