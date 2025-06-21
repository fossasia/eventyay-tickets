Talks
=====

Resource description
--------------------

The talk resource is the same as the submission resource, but will limit the returned
submissions to talks that already have a slot on the current schedule. It contains the
following public fields:

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
code                                  string                     A unique, alphanumeric identifier, also used in URLs
speakers                              list                       A list of speaker objects, e.g. ``[{"name": "Jane", "code": "ABCDEF", "biography": ""}]``
created                               string                     The time of submission creation as an ISO-8601 formatted datetime. Available if the requesting user has organiser permission.
title                                 string                     The submission's title
submission_type                       string                     The submission type (e.g. "talk", "workshop")
submission_type_id                    number                     ID of the submission type
track                                 string                     The track this talk belongs to (e.g. "security", "design", or ``null``)
track_id                              number                     ID of the track this talk belongs to (e.g. "security", "design", or ``null``)
state                                 string                     The submission's state, one of "submitted", "accepted", "rejected", "confirmed"
abstract                              string                     The abstract, a short note of the submission's content
description                           string                     The description, a more expansive description of the submission's content
duration                              number                     The talk's duration in minutes, or ``null``
do_not_record                         boolean                    Indicates if the speaker consent to recordings of their talk
is_featured                           boolean                    Indicates if the talk is show in the schedule preview / sneak peek
content_locale                        string                     The language the submission is in, e.g. "en" or "de"
slot                                  object                     An object with the scheduling details, e.g. ``{"start": …, "end": …, "room": "R101", "room_id": 12}`` if they exist. This will not be present til after the schedule is released.
slot_count                            number                     How often this submission may be scheduled.
answers                               list                       The question answers given by the speakers. Available if the requesting user has organiser permissions, and if the ``questions`` query parameter is passed.
notes                                 string                     Notes the speaker left for the organisers. Available if the requesting user has organiser permissions.
internal_notes                        string                     Notes the organisers left on the submission. Available if the requesting user has organiser permissions.
tags                                  list                       The tags attached to the current submission, as a list of strings. Available if the requesting user has organiser or reviewer permissions.
tag_ids                               list                       The tags attached to the current submission, as a list of IDs. Available if the requesting user has organiser or reviewer permissions.
===================================== ========================== =======================================================

.. versionadded:: 1.1.0
   The ``resources`` field for file uploads was added in pretalx v1.1.0.

.. versionadded:: 2.2.0
   The ``tags`` field was added in pretalx v2.2.0.

.. versionadded:: 3.0.0
   The ``track_id``, ``tag_ids`` and ``submission_type_id`` fields were added, as well as the ``room_id`` field in the ``slot`` object.

.. versionchanged:: 3.0.0
   The ``answers`` field was turned off by default in pretalx v3.0.0. Pass the ``questions`` query parameter to see questions, and pass ``questions=all`` to get the previous behaviour.

Endpoints
---------

.. http:get:: /api/events/{event}/talks

   Returns a list of all scheduled submissions the authenticated user/token has access to, or
   all confirmed, publicly scheduled submissions for unauthenticated users.
   For a list of all submissions regardless of their state, authenticated users may choose
   to use the ``/api/events/{event}/submissions`` endpoint instead.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/talks HTTP/1.1
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
            "speakers": [{"name": "Jane", "code": "DEFAB", "biography": ""}],
            "title": "A talk",
            "submission_type": "talk",
            "submission_type_id": 12,
            "state": "confirmed",
            "abstract": "A good talk.",
            "description": "I will expand upon the properties of the talk, primarily its high quality.",
            "duration": 30,
            "do_not_record": true,
            "is_featured": false,
            "content_locale": "en",
            "slot": {
              "start": "2017-12-27T10:00:00Z",
              "end": "2017-12-27T10:30:00Z",
              "room": "R101",
              "room_id": 12
            }
          },
          "answers": [
            {
              "id": 1,
              "question": {"id": 1, "question": {"en": "How much do you like green, on a scale from 1-10?"}, "required": false, "target": "submission", "options": []},
              "answer": "11",
              "answer_file": null,
              "submission": "ABCDE",
              "person": null,
              "options": []
            }
           ],
           "notes": "Please make sure you give me red M&Ms",
           "internal_notes": "Absolutely no M&Ms, but cool proposal otherwise!",
           "tags": ["science"],
           "tag_ids": [5]
        ]
      }

   :param event: The ``slug`` field of the event to fetch
   :query page: The page number in case of a multi-page result set, default is 1
   :query q: Search through submissions by title and speaker name
   :query submission_type: Filter submissions by submission type
   :query state: Filter submission by state
   :query questions: Pass a comma separated list of question IDs to load, or the string 'all' to return all answers.
   :query is_featured: Filter by the ``is_featured`` field (``true`` or ``false``).

.. http:get:: /api/events/(event)/talks/{code}

   Returns information on one event, identified by its slug.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/talks/ABCDE HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      {
        "code": "ABCDE",
        "speakers": [{"name": "Jane", "code": "DEFAB", "biography": ""}],
        "title": "A talk",
        "submission_type": "talk",
        "submission_type_id": 12,
        "state": "confirmed",
        "abstract": "A good talk.",
        "description": "I will expand upon the properties of the talk, primarily its high quality.",
        "duration": 30,
        "do_not_record": true,
        "is_featured": false,
        "content_locale": "en",
        "slot": {
          "start": "2017-12-27T10:00:00Z",
          "end": "2017-12-27T10:30:00Z",
          "room": "R101",
          "room_id": 12
        },
        "answers": [
          {
            "id": 1,
            "question": {"id": 1, "question": {"en": "How much do you like green, on a scale from 1-10?"}, "required": false, "target": "submission", "options": []},
            "answer": "11",
            "answer_file": null,
            "submission": "ABCDE",
            "person": null,
            "options": []
          }
         ],
         "notes": "Please make sure you give me red M&Ms",
         "internal_notes": "Absolutely no M&Ms, but cool proposal otherwise!",
         "tags": ["science"],
         "tag_ids": [5]
      }

   :param event: The ``slug`` field of the event to fetch
   :param code: The ``code`` field of the submission to fetch
   :query questions: Pass a comma separated list of question IDs to load, or the string 'all' to return all answers.
   :statuscode 200: no error
   :statuscode 401: Authentication failure
   :statuscode 403: The requested event does not exist **or** you have no permission to view it.
