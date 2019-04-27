.. _configure:

Configuration
=============

You can configure pretalx using config files or environment variables. You can
combine those two options, and their precedence is in this order:

1. Environment variables
2. Configuration files
    - The config file in the environment variable ``PRETALX_CONFIG_FILE`` if present, **or**:
    - The following three configuration files in this order:
       - The config file ``pretalx.cfg`` in the ``src`` directory, next to the ``pretalx.example.cfg`` file.
       - The config file ``~/.pretalx.cfg`` in the home of the executing user.
       - The config file ``/etc/pretalx/pretalx.cfg``
5. Sensible defaults


This page explains the options grouped by configuration file sections. You'll
find the environment variable next to their corresponding settings.  A config
file looks like this:

.. literalinclude:: ../../src/pretalx.example.cfg
   :language: ini

The filesystem section
----------------------

``data``
~~~~~~~~

- The ``data`` option describes the path that is the base for all other
  directories. pretalx will also save its log files there. Unless you have a
  compelling reason to keep other files apart, setting the ``data`` option is
  the easiest way to configure file storage.
- **Environment variable:** ``PRETALX_DATA_DIR``
- **Default:** A directory called ``data`` next to pretalx's ``manage.py``.

``media``
~~~~~~~~~

- The ``media`` option sets the media directory that contains user generated files. It needs to
  be writeable by the pretalx process.
- **Environment variable:** ``PRETALX_FILESYSTEM_MEDIA``
- **Default:** A directory called ``media`` in the ``data`` directory (see above).

``logs``
~~~~~~~~

- The ``logs`` option sets the log directory that contains logged data. It needs to
  be writeable by the pretalx process.
- **Environment variable:** ``PRETALX_FILESYSTEM_LOGS``
- **Default:** A directory called ``logs`` in the ``data`` directory (see above).

``static``
~~~~~~~~~~

- The ``statics`` option sets the directory that contains static files. It needs to
  be writeable by the pretalx process. pretalx will put files there during the ``rebuild`` and
  ``collectstatic`` commands.
- **Environment variable:** ``PRETALX_FILESYSTEM_STATIC``
- **Default:** A directory called ``static.dist`` next to pretalx's ``manage.py``.

The site section
----------------

``debug``
~~~~~~~~~

- Decides if pretalx runs in debug mode. Please use this mode for development and debugging, not
  for live usage.
- **Environment variable:** ``PRETALX_DEBUG``
- **Default:** ``True`` if you're executing ``runserver``, ``False`` otherwise. **Never run a
  production server in debug mode.**

``url``
~~~~~~~

- pretalx uses this value when it has to render full URLs, for example in
  emails or feeds. It is also used to determined the allowed incoming hosts.
- **Environment variable:** ``PRETALX_SITE_URL``
- **Default:** ``http://localhost``

``secret``
~~~~~~~~~~

- Every Django application has a secret that Django uses for cryptographic signing.
  You do not need to set this variable – pretalx will generate a secret key and save it in a local file if
  you do not set it.
- **Default:** None


The database section
--------------------

``backend``
~~~~~~~~~~~

- pretalx supports most SQL databases. You'll need to install the appropriate
  Python library for each of them, as described in the table below. The default
  is SQLite, which is *not* a production database. Please use a database like
  PostgresQL or MySQL.
- **Environment variable:** ``PRETALX_DB_TYPE``
- **Default:** ``sqlite3``

+------------+----------------------+---------------------+
| Database   | Configuration string | pip package         |
+============+======================+=====================+
| PostgresQL | ``postgresql``       | ``psycopg2-binary`` |
+------------+----------------------+---------------------+
| MySQL      | ``mysql``            | ``mysqlclient``     |
+------------+----------------------+---------------------+
| SQLite     | ``sqlite3``          | –                   |
+------------+----------------------+---------------------+
| Oracle     | ``oracle``           | ``cx_Oracle``       |
+------------+----------------------+---------------------+

``name``
~~~~~~~~

- The database's name.
- **Environment variable:** ``PRETALX_DB_NAME``
- **Default:** ``''``

``user``
~~~~~~~~

- The database user, if applicable.
- **Environment variable:** ``PRETALX_DB_USER``
- **Default:** ``''``

``password``
~~~~~~~~~~~~

- The database password, if applicable.
- **Environment variable:** ``PRETALX_DB_PASS``
- **Default:** ``''``

``host``
~~~~~~~~

- The database host, or the socket location, as needed..
- **Environment variable:** ``PRETALX_DB_HOST``
- **Default:** ``''``

``port``
~~~~~~~~

- The database port, if applicable.
- **Environment variable:** ``PRETALX_DB_PORT``
- **Default:** ``''``

The mail section
----------------

``from``
~~~~~~~~

- The fall-back sender address, e.g. for when pretalx sends event independent emails.
- **Environment variable:** ``PRETALX_MAIL_FROM``
- **Default:** ``admin@localhost``

``host``
~~~~~~~~

- The email server host address.
- **Environment variable:** ``PRETALX_MAIL_HOST``
- **Default:** ``localhost``

``port``
~~~~~~~~

- The email server port.
- **Environment variable:** ``PRETALX_MAIL_PORT``
- **Default:** ``25``

``user``
~~~~~~~~

- The user account for mail server authentication, if needed.
- **Environment variable:** ``PRETALX_MAIL_USER``
- **Default:** ``''``

``password``
~~~~~~~~~~~~

- The password for mail server authentication, if needed.
- **Environment variable:** ``PRETALX_MAIL_PASSWORD``
- **Default:** ``''``

``tls``
~~~~~~~

- Should pretalx use TLS when sending mail? Please choose either TLS or SSL.
- **Environment variable:** ``PRETALX_MAIL_TLS``
- **Default:** ``False``

``ssl``
~~~~~~~

- Should pretalx use SSL when sending mail? Please choose either TLS or SSL.
- **Environment variable:** ``PRETALX_MAIL_SSL``
- **Default:** ``False``

The celery section
------------------

Celery is not a requirement for pretalx. Celery runs as a separate process, and
allows you to execute long-running tasks away from the usual request-response
cycle.

``backend``
~~~~~~~~~~~

- The celery backend. If you use a standard redis-based setup,
  ``'redis://127.0.0.1/1'`` would be a sensible value.
- **Environment variable:** ``PRETALX_CELERY_BACKEND``
- **Default:** ``''``

``broker``
~~~~~~~~~~~

- The celery broker. If you use a standard redis-based setup,
  ``'redis://127.0.0.1/2'`` would be a sensible value.
- **Environment variable:** ``PRETALX_CELERY_BROKER``
- **Default:** ``''``

The redis section
-----------------

If you configure a redis server, pretalx can use it for locking, caching and
session storage to speed up operations. You will need to install ``django_redis``.

``location``
~~~~~~~~~~~~

- The location of redis, if you want to use it as a cache.
  ``'redis://[:password]@127.0.0.1:6397/1'`` would be a sensible value, or
  ``unix://[:password]@/path/to/socket.sock?db=0`` if you prefer to use sockets.
- **Environment variable:** ``PRETALX_REDIS``
- **Default:** ``''``

``session``
~~~~~~~~~~~

- If you want to use redis as your session storage, set this to ``True``.
  ``'redis://127.0.0.1/2'`` would be a sensible value.
- **Environment variable:** ``PRETALX_REDIS_SESSIONS``
- **Default:** ``False``

The logging section
-------------------

``email``
~~~~~~~~~

- The email address (or addresses, comma separated) to send system logs to.
- **Environment variable:** ``PRETALX_LOGGING_EMAIL``
- **Default:** ``''``

``email_level``
~~~~~~~~~~~~~~~

- The log level to start sending emails at. Any of ``[DEBUG, INFO, WARNING, ERROR, CRITICAL]``.
- **Environment variable:** ``PRETALX_LOGGING_EMAIL_LEVEL``
- **Default:** ``'ERROR'``

The locale section
------------------

``language_code``
~~~~~~~~~~~~~~~~~

- The system's default locale.
- **Environment variable:** ``PRETALX_LANGUAGE_CODE``
- **Default:** ``'en'``

``time_zone``
~~~~~~~~~~~~~

- The system's default time zone as a ``pytz`` name.
- **Environment variable:** ``PRETALX_TIME_ZONE``
- **Default:** ``'UTC'``
