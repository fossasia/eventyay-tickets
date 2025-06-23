from .settings import *  # noqa

CHANNEL_LAYERS["default"]["CONFIG"]["hosts"][0]["db"] = 10  # noqa
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa
