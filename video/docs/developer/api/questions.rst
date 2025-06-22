Questions
=========

Users can ask questions in a room, which need to be approved by a moderator and then can be read and upvoted by other users. Questions can be marked as answered.
Asking questions can be locked per room to only allow questions at a certain time.
To clear questions after or before a logical session, single questions can be deleted ("delete all" to be implemented by the client).

Model::

    {
        id: uuid,
        room_id: uuid,
        sender: uuid,
        timestamp: Datetime,
        content: String,
        state: String, // 'mod_queue', 'visible', 'archived'
        answered: Boolean,
        is_pinned: Boolean,
        score: Number,
        voted: Boolean // has the current user voted on the question? Available on list actions.
    }

Permissions
-----------

There are four permissions involved with the questions API:

- ``room:question.read`` to be able to see questions at all
- ``room:question.ask`` to be able to ask questions
- ``room:question.vote`` to be able to vote on questions
- ``room:question.moderate`` to be able to update or delete questions, and to activate and deactivate the questions module

Room Config
-----------

To enable questions for a room, add the questions module to the room modules::

    {
        "name": "Room with questions",
        "modules": [{
            type: 'question',
            config: {
                active: true,  // false by default
                requires_moderation: false  // true by default
            }
        }],
        …
    }

## ``question.ask``

To ask a question, send a message like this::

    => ["question.ask", 1234, {"room": "room_0", "content": "What is your favourite colour?"}]
    <- ["success", 1234, {"question": {…}}]
    <= ["question.created_or_updated", {"question": {…}}]

On creates and on updates, all people in the room who have the required access rights will receive a message like this::

    <= ["question.created_or_updated", {"question": {…}}]

## ``question.update``

To update a question (only permitted for moderators), send a message like this::

    => ["question.update", 1234, {"room": 123, "id": "UUID", "state": "visible"}]
    <- ["success", 1234, {"question": {…}}]
    <= ["question.created_or_updated", {"question": {…}}]

## ``question.list``

Given a room ID, return all the questions that are visible to the user::

    => ["question.list", 1234, {"room": "room_0"}]
    <- ["success", 1234, [{"id": }, ...]

Note that the question object has an added ``voted`` boolean attribute denoting
if the current user has voted for this question.

## ``question.vote``

Given a room ID and a question ID, users can add their ``vote: true`` or remove it with ``vote: false``::

    => ["question.vote", 1234, {"room": "room_0", "id": 12, "vote": true}]
    <- ["success", 1234, [{"id": }, ...]

## ``question.delete``

Only moderators may delete questions. Delete notifications are broadcasted like this::

    => ["question.delete", 1234, {"room": "room_0", "id": 12}]
    <- ["success", 1234, [{"id": }, ...]
    <= ["question.deleted", {"room": "room_0", "id": 12}]

## ``question.pin``, ``question.unpin``

Only moderators may pin questions, like this::

    => ["question.pin", 1234, {"room": "room_0", "id": 12}]
    <- ["success", 1234, [{"id": }, ...]
    <= ["question.pinned", {"room": "room_0", "id": 12}]

Unpinning doesn't need a question ID::

    => ["question.unpin", 1234, {"room": "room_0"}]
    <- ["success", 1234, [{}, ...]
    <= ["question.unpinned", {"room": "room_0"}]


TODOs
-----

- add moderator command ``question.activate`` that updates the module config
