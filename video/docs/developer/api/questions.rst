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

Permissions
-----------

There are four permissions involved with the questions API:

- `room:questions.read` to be able to see questions at all
- `room:questions.ask` to be able to ask questions
- `room:questions.vote` to be able to vote on questions
- `room:questions.moderate` to be able to update or delete questions, and to activate and deactivate the questions module

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

TODOs
-----

- add moderator command `questions.activate` that updates the module config
