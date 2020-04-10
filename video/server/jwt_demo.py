import datetime
import jwt

secret = "FaZaa4KeeZoo2ahgoh2uenahd3Uta4Ei"
issuer = "https://pretix.eu/"
audience = "demo-event"


def create_token(user_id, traits):
    iat = datetime.datetime.utcnow()
    exp = iat + datetime.timedelta(days=999)
    payload = {
        "iss": issuer,
        "aud": audience,
        "exp": exp,
        "iat": iat,
        "uid": user_id,
        "traits": traits
    }
    token = jwt.encode(
        payload, secret, algorithm="HS256"
    ).decode("utf-8")
    return token


def decode_token(token):
    return jwt.decode(token, secret, algorithm="HS256", audience=audience, issuer=issuer)


print("creating token")
token = create_token("some-user-id", ["speaker", "addon-2"])
print(token)
print("verifying token")
print(decode_token(token))
