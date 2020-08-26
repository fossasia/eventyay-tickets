Answers
=======

.. versionadded:: 2.0.0
   This resource endpoint.

Resource description
--------------------

The answers resource represents all data collected by organizers via the flexible questions model, that
allows for nearly arbitrary data collection from speakers or reviewers. The answers endpoint includes
minimal information on the question answered: just the ID and the question. For further details, please
refer to the ``questions/`` endpoint.

The answers resource contains the following public fields:

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
id                                    number                     The unique ID of the question object
answer                                string                     The kind of question asked. Can be any of ``number``, ``string``, ``text``, ``boolean``, ``file``, ``choices``, ``multiple_choice``.
answer_file                           string                     The URL of the uploaded file
question                              object                     An object with two fields: ``id`` (a number) and ``question`` (a multi-lingual string)
submission                            string                     If the answer is tied to a submission, the submission's code
review                                number                     If the answer is tied to a review, the review's ID
person                                string                     If the answer is tied to a speaker, the speaker's ID
options                               list                       If the answer consists of one or several options, the options in an object, containing the keys ``id`` and ``option``.
===================================== ========================== =======================================================

Permissions and limitations
---------------------------

This endpoint is writable. However, it does not support the full spectrum of question capabilities, namely:

- You cannot answer or change choice questions
- You cannot answer or change file upload questions
- There is currently no API validation that the answer conforms to the question type, e.g. that number questions are answered with numbers

.. note::
   These limitations are not by design, they are by capacity.
   If you would like to see these features in pretalx, you can `contribute <contributing>` them or provide `funding <funding>`!

Endpoints
---------

.. http:get:: /api/events/{event}/answers/

   Returns a list of all answers provided for this event.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/answers/ HTTP/1.1
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
               "question": {
                   "id": 1,
                   "question": {
                       "en": "How much do you like green, on a scale from 1-10?"
                   }
               },
               "answer": "11",
               "answer_file": null,
               "submission": "VTJQY8",
               "review": null,
               "person": null,
               "options": []
            }
        ]
      }

   :param event: The ``slug`` field of the event to fetch
   :query page: The page number in case of a multi-page result set, default is 1
   :query q: Search for a string in the answers
   :query question: Filter for answers to a specific question, by its ID
   :query submission: Filter for answers to a specific submission, by its code
   :query review: Filter for answers to a specific review, by its ID
   :query person: Filter for answers by a specific person, by their code

.. http:get:: /api/events/(event)/answers/{id}/

   Returns information on one question, identified by its ID.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/answers/1 HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      {
         "id": 1,
         "question": {
             "id": 1,
             "question": {
                 "en": "How much do you like green, on a scale from 1-10?"
             }
         },
         "answer": "11",
         "answer_file": null,
         "submission": "VTJQY8",
         "review": null,
         "person": null,
         "options": []
      }

   :param event: The ``slug`` field of the event to fetch
   :param code: The ``id`` field of the question to fetch
   :statuscode 200: no error
   :statuscode 401: Authentication failure
