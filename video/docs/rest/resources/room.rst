Room
====

Resource description
--------------------

The world resource contains the following public fields:

.. rst-class:: rest-resource-table

===================================== ========================== =======================================================
Field                                 Type                       Description
===================================== ========================== =======================================================
id                                    string                     The world's ID
name                                  string                     A title for the room
description                           string                     A markdown-compatible description of the room
module_config                         list                       Room content configuration
permission_config                     object                     Permission rules mapping permission keys to lists of
                                                                 traits
sorting_priority                      integer                    An arbitrary integer used for sorting
===================================== ========================== =======================================================

Endpoints
---------

.. http:get:: /api/v1/worlds/(world_id)/rooms/

   Returns all rooms in the world (that you are allowed to see)

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/worlds/sample/rooms/ HTTP/1.1
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
            "id": "eaa91024-1278-468d-8f24-31479817b073",
            "name": "Forum",
            "description": "Main room",
            "module_config": [
              {
                "type": "chat.native"
              }
            ],
            "permission_config": {},
            "domain": "sample.venueless.events"
          }
        ]
      }

   :statuscode 200: no error
   :statuscode 401: Authentication failure
   :statuscode 403: The world or room does not exist **or** you have no permission to view it.

.. http:get:: /api/v1/worlds/(world_id)/rooms/(room_id)/

   Returns details on a specific room

   **Example request**:

   .. sourcecode:: http

      GET /api/v1/worlds/sample/rooms/eaa91024-1278-468d-8f24-31479817b073/ HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      {
        "id": "eaa91024-1278-468d-8f24-31479817b073",
        "name": "Forum",
        "description": "Main room",
        "module_config": [
          {
            "type": "chat.native"
          }
        ],
        "permission_config": {},
        "domain": "sample.venueless.events"
      }

   :statuscode 200: no error
   :statuscode 401: Authentication failure
   :statuscode 403: The world or room does not exist **or** you have no permission to view it.

.. http:post:: /api/v1/worlds/(world_id)/rooms/

   Creates a room

   **Example request**:

   .. sourcecode:: http

      POST /api/v1/worlds/sample/ HTTP/1.1
      Accept: application/json, text/javascript
      Content-Type: application/json

      {
        "name": "Quiet room",
        "description": "Main room",
        "module_config": [
          {
            "type": "chat.native"
          }
        ],
        "permission_config": {},
        "domain": "sample.venueless.events"
      }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

      {
        "id": "eaa91024-1278-468d-8f24-31479817b073",
        "name": "Quiet room",
        "description": "Main room",
        "module_config": [
          {
            "type": "chat.native"
          }
        ],
        "permission_config": {},
        "domain": "sample.venueless.events"
      }

   :statuscode 200: no error
   :statuscode 400: The world could not be updated due to invalid submitted data.
   :statuscode 401: Authentication failure
   :statuscode 403: The requested world does not exist **or** you have no permission to create this resource.

.. http:patch:: /api/v1/worlds/(world_id)/rooms/(room_id)/

   Updates a room

   **Example request**:

   .. sourcecode:: http

      PATCH /api/v1/worlds/sample/ HTTP/1.1
      Accept: application/json, text/javascript
      Content-Type: application/json

      {
        "name": "Quiet room"
      }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      {
        "id": "eaa91024-1278-468d-8f24-31479817b073",
        "name": "Quiet room",
        "description": "Main room",
        "module_config": [
          {
            "type": "chat.native"
          }
        ],
        "permission_config": {},
        "domain": "sample.venueless.events"
      }

   :statuscode 200: no error
   :statuscode 400: The world could not be updated due to invalid submitted data.
   :statuscode 401: Authentication failure
   :statuscode 403: The requested world/room does not exist **or** you have no permission to update this resource.

.. http:delete:: /api/v1/worlds/(world_id)/rooms/(room_id)/

   Deletes a room

   **Example request**:

   .. sourcecode:: http

      PATCH /api/v1/worlds/sample/ HTTP/1.1
      Accept: application/json, text/javascript
      Content-Type: application/json

      {
        "name": "Quiet room"
      }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Content
      Vary: Accept

   :statuscode 200: no error
   :statuscode 401: Authentication failure
   :statuscode 403: The requested world/room does not exist **or** you have no permission to delete this resource.
