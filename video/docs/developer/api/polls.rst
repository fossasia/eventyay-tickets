Polls
=====

Moderators can create polls, which are visible while they are "open" or
"closed" and only visible to moderators while they are in "draft" or "archived"
state.

Posting polls can be locked per room to only allow polls at a certain time.  To
clear polls after or before a logical session, single polls can be deleted or
archived ("delete all" to be implemented by the client)::

    {
	id: uuid,
	room_id: uuid,
	timestamp: Datetime,
	content: String,
	state: String, // 'open', 'closed', 'draft', 'archived'
        poll_type: String, // 'choice', 'multi'
        results: Object,
        is_pinned: Boolean,
        options: [
            {
                id: uuid,
                content: String,
                order: Integer,
            }
        ]
        answered: List // answers the current user has posted, available on list actions
    }

Permissions
-----------

There are three permissions involved with the polls API:

- ``room:poll.read`` to be able to see polls at all
- ``room:poll.vote`` to be able to vote on polls
- ``room:poll.manage`` to be able to update or delete polls, and to activate and deactivate the polls module

Room Config
-----------

To enable polls for a room, add the polls module to the room modules::

    {
        "name": "Room with polls",
        "modules": [{
            type: 'poll',
            config: {
                active: true,  // false by default
                requires_moderation: false  // true by default
            }
        }],
        …
    }

## ``poll.create``

To create a poll, send a message like this::

    => ["poll.create", 1234, {"room": "room_0", "content": "What is your favourite colour?", options=[{"content": "Yes", "order": 1}, {"content": "No", "order": 2}]}]
    <- ["success", 1234, {"poll": {…}}]
    <= ["poll.created_or_updated", {"poll": {…}}]

On creates and on updates, all people in the room who have the required access rights will receive a message like this::

    <= ["poll.created_or_updated", {"poll": {…}}]

## ``poll.update``

To update a poll (only permitted for moderators), send a message like this::

    => ["poll.update", 1234, {"room": 123, "id": "UUID", "state": "visible"}]
    <- ["success", 1234, {"poll": {…}}]
    <= ["poll.created_or_updated", {"poll": {…}}]

To change the options, adjust the ``"options"``. To update an option, remember
to include its ID, to remove it, drop it from the options list, and to add a
new option, add it to the list without an ID.

## ``poll.list``

Given a room ID, return all the polls that are visible to the user::

    => ["poll.list", 1234, {"room": "room_0"}]
    <- ["success", 1234, [{"id": }, ...]

Note that the poll object has an added ``answers``  # TODO wtf is in there?
boolean attribute denoting how the user has answered this poll.

## ``poll.vote``

Given a room ID and a poll ID, users can select one or multiple options as a list of IDs::

    => ["poll.vote", 1234, {"room": "room_0", "id": 12, "options": ["ed1", "ed2"]}]
    <- ["success", 1234, [{"id": }, ...]

## ``poll.delete``

Only moderators may delete polls. Delete notifications are broadcasted like this::

    => ["poll.delete", 1234, {"room": "room_0", "id": 12}]
    <- ["success", 1234, [{"id": }, ...]
    <= ["poll.deleted", {"room": "room_0", "id": 12}]

## ``poll.pin``

Only moderators may pin polls, like this::

    => ["poll.pin", 1234, {"room": "room_0", "id": 12}]
    <- ["success", 1234, [{"id": }, ...]
    <= ["poll.pinned", {"room": "room_0", "id": 12}]
