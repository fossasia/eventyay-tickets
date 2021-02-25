Tags
====

.. versionadded:: 2.2.0
   This resource endpoint.

Resource description
--------------------

The tag resource contains the following fields (currently limited to organisers and reviewers):

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
tag                                   string                     The actual tag name.
description                           multi-lingual string       The description of the tag.
color                                 string                     The tag's color as hex string.
===================================== ========================== =======================================================

Endpoints
---------

.. http:get:: /api/events/{event}/tags/

   Returns a list of all tags configured for this event.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/tags/ HTTP/1.1
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
            "tag": "science",
            "description": {"en": "Scientific sessions"},
            "color": "#00ff00",
          }
        ]
      }

   :param event: The ``slug`` field of the event to fetch
   :query page: The page number in case of a multi-page result set, default is 1

.. http:get:: /api/events/(event)/tags/{tag}/

   Returns information on one tag, identified by its tag string.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/tags/science HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

       {
         "tag": "science",
         "description": {"en": "Scientific sessions"},
         "color": "#00ff00",
       }

   :param event: The ``slug`` field of the event to fetch
   :param code: The ``tag`` field of the tag to fetch
   :statuscode 200: no error
   :statuscode 401: Authentication failure
