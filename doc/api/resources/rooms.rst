Rooms
=====

.. versionadded:: 0.9.0
   This resource endpoint.

Resource description
--------------------

The room resource contains the following public fields:

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
id                                    number                     The unique ID of the room object
name                                  string                     The name of the room
description                           string                     The description of the room
capacity                              number                     How many people fit in the room
position                              number                     A number indicating the ordering of the room relative to other rooms, e.g. in schedule visualisations
speaker_info                          string                     Additional information for speakers. Only present when requested by an organiser
availabilities                        list                       A list of objects with a ``start`` and ``end`` attribute, both datetimes. Only present when requested by an organiser
===================================== ========================== =======================================================

Endpoints
---------

.. http:get:: /api/events/{event}/rooms

   Returns a list of all rooms configured for this event.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/rooms HTTP/1.1
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
            "name": "R101",
            "description": "Next to the entrance",
            "capacity": 50,
            "position": 10
          }
        ]
      }

   :param event: The ``slug`` field of the event to fetch
   :query page: The page number in case of a multi-page result set, default is 1

.. http:get:: /api/events/(event)/rooms/{id}

   Returns information on one room, identified by its ID.

   **Example request**:

   .. sourcecode:: http

      GET /api/events/sampleconf/rooms/23 HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

       {
         "id": 23,
         "name": "R101",
         "description": "Next to the entrance",
         "capacity": 50,
         "position": 10
       }

   :param event: The ``slug`` field of the event to fetch
   :param code: The ``id`` field of the room to fetch
   :statuscode 200: no error
   :statuscode 401: Authentication failure
