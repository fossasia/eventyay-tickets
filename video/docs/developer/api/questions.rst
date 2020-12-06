Questions
=========

Users can ask questions in a room, which need to be approved by a moderator and then can be read and upvoted by other users. Questions can be marked as answered.
Asking questions can be locked per room to only allow questions at a certain time.
To clear questions after or before a logical session, single questions can be deleted ("delete all" to be implemented by the client).

```
{
	id: uuid,
	room_id: ,
	user: Number,
	timestamp: Datetime,
	content: String,
	state/visible_to: String, // 'to_be_moderated', 'visible', 'archived'
	answered: Boolean,
	votes: Number
}
```

Room Config
-----------

To enable questions for a room, add the questions module to the room modules.

```
{
		"name": "Room with questions",
		"modules": [{
			type: 'questions',
			config: {
				active: true,  // false by default
				requires_moderation: false  // true by default
			}
		}],
		…
}
```

## `question.create`

## `question.update`

## `question.vote`
up or none

## `question.delete`

## `question.lock`

TODOs
-----

- permissions
- module config (somehow signal that questions are enabled in a room)
- keep deleted questions for archival and replay, or wait until unified event stream is implemented?
