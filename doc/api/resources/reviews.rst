Reviews
=======

.. versionadded:: 0.9.0
   This resource endpoint.

Resource description
--------------------

The review resource contains the following public fields:

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
id                                    number                     The unique ID of the review object
submission                            string                     The unique code of the submission the review relates to
user                                  object                     The ``name`` and ``email`` of the reviewing user.
text                                  string                     The review's text
score                                 number                     The review's score
override_vote                         boolean                    ``true`` if the review is a positive override vote, ``false`` if the review is a negative override vote, ``null`` otherwise
created                               datetime                   The review's creation timestamp
updated                               datetime                   The review's last change timestamp
answers                               list                       The question answers given by the reviewer.
===================================== ========================== =======================================================

Endpoints
---------

.. http:get:: /api/events/{event}/reviews

   Returns a list of all reviews the authenticated user/token has access to.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/reviews HTTP/1.1
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
            "id": 23,
            "submission": "ABCDE",
            "user": {"name": "Jane", "email": "jane.doe@gmail.com"},
            "text": "This is a good submission",
            "score": 10,
            "override_vote": null,
            "created": 
            "updated": 
            "answers": [
              {
                "id": 1,
                "question": {"id": 1, "question": {"en": "How much would you like to see this talk?"}, "required": false, "target": "review", "options": []},
                "answer": "11",
                "answer_file": null,
                "review": 23,
                "person": null,
                "options": []
              }
             ]
          }
        ]
      }

   :param event: The ``slug`` field of the event to fetch
   :query page: The page number in case of a multi-page result set, default is 1
   :query submission__code: Filter reviews by the code of their submission

.. http:get:: /api/events/(event)/reviews/{id}

   Returns information on one review, identified by its ID.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/reviews/23 HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

       {
         "id": 23,
         "submission": "ABCDE",
         "user": {"name": "Jane", "email": "jane.doe@gmail.com"},
         "text": "This is a good submission",
         "score": 10,
         "override_vote": null,
         "created": 
         "updated": 
         "answers": [
           {
             "id": 1,
             "question": {"id": 1, "question": {"en": "How much would you like to see this talk?"}, "required": false, "target": "review", "options": []},
             "answer": "11",
             "answer_file": null,
             "review": 23,
             "person": null,
             "options": []
           }
          ]
       }

   :param event: The ``slug`` field of the event to fetch
   :param code: The ``id`` field of the review to fetch
   :statuscode 200: no error
   :statuscode 401: Authentication failure
   :statuscode 403: The requested event does not exist **or** you have no permission to view it.
