Questions
=========

.. versionadded:: 2.0.0
   This resource endpoint.

Resource description
--------------------

The questions resource represents the highly flexible questions model that allows organisers to request
nearly arbitrary additional information from speakers or reviewers. You will sometimes find questions
nested in other information, such as in answers – in that case, only the ``id`` and ``question`` fields
will be included to reduce the transmission size.

The questions resource contains the following public fields:

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
id                                    number                     The unique ID of the question object
variant                               string                     The kind of question asked. Can be any of ``number``, ``string``, ``text``, ``boolean``, ``file``, ``choices``, ``multiple_choice``.
target                                string                     The question scope. Can be ``speaker`` (each speaker is asked once), ``submission`` (speakers are asked per submission), or ``reviewer`` (the question is used in the review process).
question                              multi-lingual string       The question
help_text                             multi-lingual string       Additional text shown to help with the question. Can be Markdown.
required                              boolean                    Are speakers required to answer the question to proceed?
options                               list                       A list of objects with an ``id`` and an ``option`` attribute, for choice questions
default_answer                        string                     The answer suggested to speakers
contains_personal_data                boolean                    If an answer contains personal data, it is deleted when a speaker deletes their account.
min_length                            number                     Minimum answer length, for text questions
max_length                            number                     Maximum answer length, for text questions
is_public                             boolean                    Is the answer shown publicly on the talk/speaker page?
is_visible_to_reviewers               boolean                    Can reviewers see the answers to this question?
===================================== ========================== =======================================================

Permissions and limitations
---------------------------

This endpoint is writable. However, it does not support the full spectrum of question capabilities, namely:

- You cannot limit a question to tracks or submission types
- You cannot change or create question options (for choice and multiple-choice questions)
- You cannot change the order of questions

.. note::
   These limitations are not by design, they are by capacity.
   If you would like to see these features in pretalx, you can `contribute <contributing>` them or provide `funding <funding>`!

Endpoints
---------

.. http:get:: /api/events/{event}/questions/

   Returns a list of all questions configured for this event.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/questions/ HTTP/1.1
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
                "id": 1,
                "variant": "number",
                "question": "How much do you like green, on a scale from 1-10?",
                "required": false,
                "target": "submission",
                "options": [],
                "help_text": null,
                "tracks": [],
                "submission_types": [],
                "default_answer": null,
                "contains_personal_data": false,
                "min_length": null,
                "max_length": null,
                "is_public": false,
                "is_visible_to_reviewers": true
            }
        ]
      }

   :param event: The ``slug`` field of the event to fetch
   :query page: The page number in case of a multi-page result set, default is 1
   :query q: Search for a string in the questions
   :query target: Filter for questions of a specific target kind, eg reviewer questions
   :query variant: Filter for questions of a specific variant, eg number questions
   :query is_public: Filter for questions that are or are not public
   :query is_visible_to_reviewers: Filter for questions that are or are not visible to reviewers
   The page number in case of a multi-page result set, default is 1

.. http:get:: /api/events/(event)/questions/{id}/

   Returns information on one question, identified by its ID.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/questions/23 HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      {
          "id": 1,
          "variant": "number",
          "question": "How much do you like green, on a scale from 1-10?",
          "required": false,
          "target": "submission",
          "options": [],
          "help_text": null,
          "tracks": [],
          "submission_types": [],
          "default_answer": null,
          "contains_personal_data": false,
          "min_length": null,
          "max_length": null,
          "is_public": false,
          "is_visible_to_reviewers": true
      }

   :param event: The ``slug`` field of the event to fetch
   :param code: The ``id`` field of the question to fetch
   :statuscode 200: no error
   :statuscode 401: Authentication failure
