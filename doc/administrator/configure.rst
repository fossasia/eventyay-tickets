Configure pretalx
=================

You can configure pretalx in two different ways: using config files or
environment variables. You can combine those two options, and their precedence
is in this order:

1. Environment variables
2. The config file ``pretalx.cfg`` in the ``src`` directory, next to the ``pretalx.example.cfg``
   file.
3. The config file ``~/.pretalx.cfg`` in the home of the executing user.
4. The config file ``/etc/pretalx/pretalx.cfg``
5. Sensible defaults

This page explains the options by configuration file section and notes the corresponding environment
variable next to it. A config file looks like this:

.. literalinclude:: ../../src/pretalx.example.cfg
   :language: ini

The filesystem section
----------------------

``data``
~~~~~~~~

- The ``data`` option describes the path that is the base for the media files
  directory, and where pretalx will save log files. Unless you have a
  compelling reason to keep those files apart, setting the ``data`` option is
  the easiest way to configure pretalx.
- **Environment variable:** ``PRETALX_DATA_DIR``
- **Default:** A directory called ``data`` next to pretalx's ``manage.py``.

``media``
~~~~~~~~~

- The ``media`` option sets the media directory that contains user generated files. It needs to
  be writable by the pretalx process.
- **Environment variable:** ``PRETALX_FILESYSTEM_MEDIA``
- **Default:** A directory called ``media`` in the ``data`` directory (see above).

``logs``
~~~~~~~~

- The ``logs`` option sets the log directory that contains logged data. It needs to
  be writable by the pretalx process.
- **Environment variable:** ``PRETALX_FILESYSTEM_LOGS``
- **Default:** A directory called ``logs`` in the ``data`` directory (see above).

``static``
~~~~~~~~~~

- The ``statics`` option sets the directory that contains static files. It needs to
  be writable by the pretalx process. pretalx will put files there during the ``rebuild`` and
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

- This value will appear whereever pretalx needs to render full URLs (for example in emails and
  feeds), and set the appropriate allowed hosts variables.
- **Environment variable:** ``PRETALX_SITE_URL``
- **Default:** ``http://localhost``

``secret``
~~~~~~~~~~

- Every Django application has a secret that Django uses for cryptographic signing.
  You do not need to set this variable – pretalx will generate a secret key and save it in a local file if
  you do not set it manually.
- **Default:** None


The database section
--------------------

``backend``
~~~~~~~~~~~

- pretalx supports most SQL databases, although you'll need to install the appropriate Python
  library for each of them, as described in the table below. The default is SQLite, which is *not* a
  production database. Please use a database like postgres or MySQL.
- **Environment variable:** ``PRETALX_DB_TYPE``
- **Default:** ``sqlite3``

+----------+----------------------+---------------------+
| Database | Configuration string | pip package         |
+==========+======================+=====================+
| Postgres | ``postgresql``       | ``psycopg2-binary`` |
+----------+----------------------+---------------------+
| MySQL    | ``mysql``            | ``mysqlclient``     |
+----------+----------------------+---------------------+
| SQLite   | ``sqlite3``          | –                   |
+----------+----------------------+---------------------+
| Oracle   | ``oracle``           | ``cx_Oracle``       |
+----------+----------------------+---------------------+

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

- The fallback sender address, e.g. for when pretalx sends event independent emails.
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

``backend``
~~~~~~~~~~~

- The celery backend. If you use a standard redis-based setup,
  ``'redis://127.0.0.1/1'`` woould be a sensible value.
- **Environment variable:** ``PRETALX_CELERY_BACKEND``
- **Default:** ``''``

``broker``
~~~~~~~~~~~

- The celery broker. If you use a standard redis-based setup,
  ``'redis://127.0.0.1/2'`` woould be a sensible value.
- **Environment variable:** ``PRETALX_CELERY_BROKER``
- **Default:** ``''``

The logging section
-------------------

``email``
~~~~~~~~~

- The email address (or addresses, comma separated) to send system logs to.
- **Environment variable:** ``PRETALX_LOGGING_EMAIL``
- **Default:** ``''``

``email_level``
~~~~~~~~~~~~~~~

- The loglevel to start sending emails at. Any of ``[DEBUG, INFO, WARNING, ERROR, CRITICAL]``.
- **Environment variable:** ``PRETALX_LOGGING_EMAIL_LEVEL``
- **Default:** ``'ERROR'``
