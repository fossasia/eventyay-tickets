import random
import string
from pathlib import Path

USE_TZ = False

SECRET_KEY = "".join(random.sample(string.printable, 20))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "dev.db",
    },
}

INSTALLED_APPS = [
    "django_markup",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            Path(__file__).parent / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
            ],
        },
    },
]
