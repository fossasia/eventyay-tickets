Events
======

Resource description
--------------------

The event resource contains the following public fields:

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
name                                  multi-lingual string       The event's full name
slug                                  string                     A short form of the name, used e.g. in URLs.
is_public                             boolean                    If ``true``, the event is publicly visible.
date_from                             datetime                   The event's start date
date_to                               datetime                   The event's end date (or ``null``)
timezone                              string                     The event's chosen timezone
===================================== ========================== =======================================================

Endpoints
---------

.. http:get:: /api/events/

   Returns a list of all events the authenticated user/token has access to, or
   all public events for unauthenticated users.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/ HTTP/1.1
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
            "name": {"en": "Sample Conference"},
            "slug": "sampleconf",
            "timezone": "Europe/berlin",
            "date_from": "2017-12-27T10:00:00Z",
            "date_to": null,
            "is_public": true,
          }
        ]
      }

   :query page: The page number in case of a multi-page result set, default is 1

.. http:get:: /api/events/(event)/

   Returns information on one event, identified by its slug.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/ HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      {
         "name": {"en": "Sample Conference"},
         "slug": "sampleconf",
         "timezone": "Europe/berlin",
         "date_from": "2017-12-27T10:00:00Z",
         "date_to": null,
         "is_public": true,
      }

   :param event: The ``slug`` field of the event to fetch
   :statuscode 200: no error
   :statuscode 401: Authentication failure
   :statuscode 403: The requested event does not exist **or** you have no permission to view it.
