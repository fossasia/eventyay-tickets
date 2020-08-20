BigBlueButton module
====================

To enable video calls, we integrate the BigBlueButton (BBB) software. venueless implements simple load balancing across
multiple BBB servers, which is why the frontend always needs to convert a room or call ID into an actual meeting
URL explicitly.

BBB Rooms
---------

To join the video chat for a room, a client can push a message like this::

    => ["bbb.room_url", 1234, {"room": "room_1"}]
    <- ["success", 1234, {"url": "https://…"}]
    
The response will contain an URL for the video chat. A display name needs to be set, otherwise
an error of type ``bbb.join.missing_profile`` is returned. If the BBB server can't be reached, ``bbb.failed`` is
returned.

In a room-based BBB meeting, moderator and attendee permissions are assigned based on world and room rights.

Private conversations
---------------------

If a private conversation includes a chat message referring to a call ID, you can get the call URL like this:

    => ["bbb.call_url", 1234, {"call": "f160bf4f-93c4-4b50-b348-6ef61db4dbe7"}]
    <- ["success", 1234, {"url": "https://…"}]

The response will contain an URL for the video chat. A display name needs to be set, otherwise
an error of type ``bbb.join.missing_profile`` is returned. If the BBB server can't be reached or the call does not exist
or you do not have permission to join, ``bbb.failed`` is returned.

In a private meeting, everyone has moderator rights.

Recordings
----------

If the user has the ``room:bbb.recordings`` permission, you can access recordings with the following command:

    => ["bbb.recordings", 1234, {"room": "f160bf4f-93c4-4b50-b348-6ef61db4dbe7"}]
    <- [
         "success",
         1234,
         {
           "results": [
             {
               "start": "2020-08-02T19:30:00.000+02:00",
               "end": "2020-08-02T20:30:00.000+02:00",
               "participants": "3",
               "state": "published",
               "url": "https://…"
             }
           ]
         }
       ]

The response will contain an URL for the video chat. A display name needs to be set, otherwise
an error of type ``bbb.join.missing_profile`` is returned. If the BBB server can't be reached or the call does not exist
or you do not have permission to join, ``bbb.failed`` is returned.

In a private meeting, everyone has moderator rights.
