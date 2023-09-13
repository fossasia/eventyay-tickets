.. _permissions:

Permission model
================

User types
----------

There are multiple user types:

- **Person** - A user account representing a regular attendee (or moderator, or admin) with access to the regular
  Venueless interface.

- **Anonymous user** - A "light-weight" user account representing an attendee of an in-person event with temporary
  access to specific features in specific rooms of the event.

- **Kiosk** – A user account only used internally to enable authentication for a kiosk-type display in an event venue.

The user type is relevant for some of the permission logic (see below), but also for other purposes (will determine if
a user's actions are relevant for statistical purposes, if the user shows up in lists, …).

Permissions
-----------

Permissions are static, hard-coded identifiers that identify specific actions. Currently, the following permissions
are defined::

    world:view
    world:update
    world:announce
    world:secrets
    world:api
    world:graphs
    world:rooms.create.stage
    world:rooms.create.chat
    world:rooms.create.bbb
    world:users.list
    world:users.manage
    world:chat.direct
    room:announce
    room:view
    room:update
    room:delete
    room:chat.read
    room:chat.join
    room:chat.send
    room:invite
    room:chat.moderate
    room:bbb.join
    room:bbb.moderate
    room:bbb.recordings

These strings are also exposed through the API to tell the client with operations are permitted.

Roles
-----

Roles represent a set of permissions and are defined individually for every world. As an example, these are just some
of the roles that are defined by default in a new world::

  "roles": {
    "attendee": [
      "world:view"
    ],
    "viewer": [
      "world:view",
      "room:view",
      "room:chat.read"
    ],
    "participant": [
      "world:view",
      "room:view",
      "room:chat.read",
      "room:bbb.join",
      "room:chat.send",
      "room:chat.join"
    ],
    "room_creator": [
      "world:rooms.create"
    ],
  }

Roles are not exposed to the frontend currently.

Explicit grants
---------------

A role can be granted to a user explicitly, either on the world as a whole or on a specific room.
Currently, this feature is mostly used to implement private rooms and invitations, but it could be the basis of more
dynamic permission assignments in the future. Example grants look like this::

    User 1234 is granted
      - role room_creator on private room 1, because they created it
      - role participant on private room 1, because they've been invited
    User 4345 is granted
      - role speaker on workshop room 1, because they've been granted the role by an admin
    User 7890 is granted
      - role moderator on the world, because they've been granted the role by an admin

Implicit grants and traits
--------------------------

Traits are arbitrary tokens that are contained in a user's authentication information. For example, if a user
authenticates to venueless through a ticketing system, they might have a trait for every product category they paid for.

Both the world as well as any room can define *implicit grants* based on those traits. For example if anyone with
**both** the ``pretix-product-1234`` and the ``pretix-product-5678`` should get the role ``participant`` in a room,
the configuration would look like this::

    "trait_grants": {
      "participant": ["pretix-product-1234", "pretix-product-5678"]
    }

In the configuration frontend, this would be shown as::

    pretix-product-1234, pretix-product-5678

It's also possible to have "OR"-type grants::

    "trait_grants": {
      "participant": ["pretix-event-foo", ["pretix-product-1234", "pretix-product-5678"]]
    }

In the configuration frontend, this would be shown as::

    pretix-event-foo, pretix-product-1234|pretix-product-5678

The "empty" grant applies to *all* users, regardless of their traits::

    "trait_grants": {
      "participant": []
    }

However, one exception is made here: The "empty" grant will **not** be respected for users with a user type other than
"person".