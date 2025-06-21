import configparser
import logging
import os
import sys
from configparser import RawConfigParser
from pathlib import Path

logger = logging.getLogger(__name__)


CONFIG = {
    "filesystem": {
        "base": {
            "default": Path(__file__).parent.parent.parent.parent,
        },
        "logs": {
            "default": None,
            "env": os.getenv("PRETALX_FILESYSTEM_LOGS"),
        },
        "media": {
            "default": None,
            "env": os.getenv("PRETALX_FILESYSTEM_MEDIA"),
        },
        "static": {
            "default": None,
            "env": os.getenv("PRETALX_FILESYSTEM_STATIC"),
        },
    },
    "site": {
        "name": {
            "default": "eventyay",
            "env": os.getenv("PRETALX_SITE_NAME"),
        },
        "debug": {
            "default": "runserver" in sys.argv or "devserver" in sys.argv,
            "env": os.getenv("PRETALX_DEBUG"),
        },
        "url": {
            "default": "http://localhost",
            "env": os.getenv("PRETALX_SITE_URL"),
        },
        "https": {
            "env": os.getenv("PRETALX_HTTPS"),
        },
        "cookie_domain": {
            "default": "",
            "env": os.getenv("PRETALX_COOKIE_DOMAIN"),
        },
        "core_modules": {
            "default": "",
            "env": os.getenv("PRETALX_CORE_MODULES"),
        },
        "media": {"default": "/media/", "env": os.getenv("PRETALX_SITE_MEDIA")},
        "static": {"default": "/static/", "env": os.getenv("PRETALX_SITE_STATIC")},
        "csp": {"default": "", "env": os.getenv("PRETALX_SITE_CSP")},
        "csp_script": {"default": "", "env": os.getenv("PRETALX_SITE_CSP_SCRIPT")},
        "csp_style": {"default": "", "env": os.getenv("PRETALX_SITE_CSP_STYLE")},
        "csp_img": {"default": "", "env": os.getenv("PRETALX_SITE_CSP_IMG")},
        "csp_form": {"default": "", "env": os.getenv("PRETALX_SITE_CSP_FORM")},
    },
    "database": {
        "backend": {
            "default": "sqlite3",
            "env": os.getenv("PRETALX_DB_TYPE"),
        },
        "name": {
            "env": os.getenv("PRETALX_DB_NAME"),
        },
        "user": {
            "default": "",
            "env": os.getenv("PRETALX_DB_USER"),
        },
        "password": {
            "default": "",
            "env": os.getenv("PRETALX_DB_PASS"),
        },
        "host": {
            "default": "",
            "env": os.getenv("PRETALX_DB_HOST"),
        },
        "port": {
            "default": "",
            "env": os.getenv("PRETALX_DB_PORT"),
        },
    },
    "mail": {
        "from": {
            "default": "admin@localhost",
            "env": os.getenv("PRETALX_MAIL_FROM"),
        },
        "host": {
            "default": "localhost",
            "env": os.getenv("PRETALX_MAIL_HOST"),
        },
        "port": {
            "default": "25",
            "env": os.getenv("PRETALX_MAIL_PORT"),
        },
        "user": {
            "default": "",
            "env": os.getenv("PRETALX_MAIL_USER"),
        },
        "password": {
            "default": "",
            "env": os.getenv("PRETALX_MAIL_PASSWORD"),
        },
        "tls": {
            "default": "False",
            "env": os.getenv("PRETALX_MAIL_TLS"),
        },
        "ssl": {
            "default": "False",
            "env": os.getenv("PRETALX_MAIL_SSL"),
        },
    },
    "redis": {
        "location": {
            "default": "False",
            "env": os.getenv("PRETALX_REDIS"),
        },
        "session": {
            "default": "False",
            "env": os.getenv("PRETALX_REDIS_SESSIONS"),
        },
    },
    "celery": {
        "broker": {
            "default": "",
            "env": os.getenv("PRETALX_CELERY_BROKER"),
        },
        "backend": {
            "default": "",
            "env": os.getenv("PRETALX_CELERY_BACKEND"),
        },
    },
    "logging": {
        "email": {
            "default": "",
            "env": os.getenv("PRETALX_LOGGING_EMAIL"),
        },
        "email_level": {
            "default": "",
            "env": os.getenv("PRETALX_LOGGING_EMAIL_LEVEL"),
        },
    },
    "locale": {
        "language_code": {
            "default": "en",
            "env": os.getenv("PRETALX_LANGUAGE_CODE"),
        },
        "time_zone": {
            "default": "UTC",
            "env": os.getenv("PRETALX_TIME_ZONE"),
        },
    },
    "files": {
        "upload_limit": {
            "default": 10,
            "env": os.getenv("PRETALX_FILE_UPLOAD_LIMIT"),
        }
    },
}


def read_config_files(config: RawConfigParser) -> tuple[RawConfigParser, list[str]]:
    if path_from_env := os.getenv("PRETALX_CONFIG_FILE"):
        file_path = Path(path_from_env)
        if file_path.exists():
            with file_path.open(encoding="utf-8") as fp:
                config.read_file(fp)
                config_files = [str(file_path.resolve())]
        else:
            logger.warning(
                "File specified by PRETALX_CONFIG_FILE does not exist. %s",
                path_from_env,
            )
            config_files = []
    else:
        config_files = config.read(
            [
                "/etc/pretalx/pretalx.cfg",
                Path.home() / ".pretalx.cfg",
                "pretalx.cfg",
            ],
            encoding="utf-8",
        )
    return (
        config,
        config_files or [],
    )  # .read() returns None if there are no config files


def reduce_dict(data):
    return {
        section_name: {
            key: value for key, value in section_content.items() if value is not None
        }
        for section_name, section_content in data.items()
    }


def read_layer(layer_name: str, config: RawConfigParser) -> RawConfigParser:
    config_dict = reduce_dict(
        {
            section_name: {
                key: value.get(layer_name) for key, value in section_content.items()
            }
            for section_name, section_content in CONFIG.items()
        }
    )
    config.read_dict(config_dict)
    return config


def build_config() -> tuple[RawConfigParser, list[str]]:
    config = configparser.RawConfigParser()
    config = read_layer("default", config)
    config, config_files = read_config_files(config)
    config = read_layer("env", config)
    return config, config_files
