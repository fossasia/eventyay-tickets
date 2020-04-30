# User/Account handling

Users can be authed against external resources or not


## Logging in with a token

Send JWT token, receive everything that's already known about the user.

```
=> ["authenticate", {"token": "JWTTOKEN"}]
<- ["authenticated", {"user.config": {}, "world.config": {}, "chat.channels": []}]
```

``chat.channels`` contains a list of **non-volatile** chat rooms the user is a member of. See chat module
 documentation for membership semantics.

## Change user info

```
=> ["user.update", 123, {whatever}]
<- ["success", 123, {}]
```

## Receiving info on another user

```
=> ["user.fetch", 123, {"id": "1234"}]
<- ["success", 123, {"id": "1234", "profile": {…}}]
```

If the user is unknown, error code ``user.not_found`` is returned.

## Profile updates

If your user data changes, you will receive a broadcast with your new profile. This is e.g. important if your profile
 is changed from a different connection.

```
<= ["user.updated", {"id": "1234", "profile": {…}}]
```
