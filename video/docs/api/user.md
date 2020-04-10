# User/Account handling

Users can be authed against external resources or not


## Logging in with a token

Send JWT token, receive everything that's already known about the user.

```
=> ["authenticate", {"token": "JWTTOKEN"}]
<- ["authenticated", {"user.config": {}, "event.config": {}}]
```

## Change user info

```
=> ["user.update", 123, {whatever}]
<- ["success", 123, {}]
```
