Configure pretalx
=================

There are two basic ways to configure pretalx: using config files or environment variables. You can
combine those two options, and their precedence is in this order:

1. Environment variables
2. The config file ``pretalx.cfg`` in the ``src`` directory, next to the ``pretalx.example.cfg``
   file.
3. The config file ``~/.pretalx.cfg`` in the home of the executing user.
4. The config file ``/etc/pretalx.cfg``
5. Sensible defaults

This page explains the options by configuration file section and notes the corresponding environment
variable next to it. A config file looks like this:

.. literalinclude:: ../../src/pretalx.example.cfg
   :language: ini

The filesystem section
----------------------

``data``
~~~~~~~~

- The ``data`` option describes the path that is used as base for the media files directory, and log
  files should be saved. Unless you have a compelling reason to keep those files apart, just setting
  the ``data`` option is the easiest way to configure pretalx.
- **Environment variable:** ``PRETALX_DATA_DIR``
- **Default:** A directory called ``data`` in the directory in which pretalx's ``manage.py`` is
  located.

``media``
~~~~~~~~~

- The ``media`` option sets the media directory that is used for user generated files. It needs to
  be writable by the pretalx process.
- **Default:** A directory called ``media`` in the ``data`` directory (see above).

``logs``
~~~~~~~~

- The ``logs`` option sets the log directory that is used for logged data. It needs to
  be writable by the pretalx process.
- **Default:** A directory called ``logs`` in the ``data`` directory (see above).

The site section
----------------

``debug``
~~~~~~~~~

- Decides if pretalx runs in debug mode. This mode is only meant for development and debugging, not
  for live usage.
- **Environment variable:** ``PRETALX_DEBUG``
- **Default:** ``True`` if you're executing ``runserver``, ``False`` otherwise. **Never run a
  production server in debug mode.**

``url``
~~~~~~~

- This setting is used to render links whereever pretalx needs full URLs (for example in emails and
  feeds), and set the appropriate allowed hosts variables.
- **Environment variable:** ``PRETALX_SITE_URL``
- **Default:** ``http://localhost``

``secret``
~~~~~~~~~~

- Every Django application has a secret that is used for cryptographic signing in many places.
  You do not need to set this variable – a secret key will be generated and saved in a local file if
  you do not set it manually.
- **Default:** None


The databases section
---------------------

``backend``
~~~~~~~~~~~

- pretalx supports most SQL databases, although you'll need to install the appropriate Python
  library for each of them, as described in the table below. The default is SQLite, which is *not* a
  production database. Please use a database like postgres or MySQL.
- **Environment variable:** ``PRETALX_DB_TYPE``
- **Default:** ``sqlite3``

+----------+----------------------+-----------------+
| Database | Configuration string | pip package     |
+==========+======================+=================+
| Postgres | ``postgresql``       | ``psycopg2``    |
+----------+----------------------+-----------------+
| MySQL    | ``mysql``            | ``mysqlclient`` |
+----------+----------------------+-----------------+
| SQLite   | ``sqlite3``          | –               |
+----------+----------------------+-----------------+
| Oracle   | ``oracle``           | ``cx_Oracle``   |
+----------+----------------------+-----------------+

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
- **Environment variable:** ``PRETALX_DB_PASSWORD``
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

- The sender address used when no other is configured, or when event independent emails are sent.
- **Environment variable:** ``PRETALX_MAIL_FROM``
- **Default:** ``admin@localhost``

``host``
~~~~~~~~

- The host on which the mail server can be reached.
- **Environment variable:** ``PRETALX_MAIL_HOST``
- **Default:** ``localhost``

``port``
~~~~~~~~

- The port on which the mail server can be reached.
- **Environment variable:** ``PRETALX_MAIL_PORT``
- **Default:** ``25``

``user``
~~~~~~~~

- The user that should be used for mail server authentication, if needed.
- **Environment variable:** ``PRETALX_MAIL_USER``
- **Default:** ``''``

``password``
~~~~~~~~~~~~

- The password that should be used for mail server authentication, if needed.
- **Environment variable:** ``PRETALX_MAIL_PASSWORD``
- **Default:** ``''``

``tls``
~~~~~~~

- Should TLS be used when sending mail? Only one of TLS and SSL may be used.
- **Environment variable:** ``PRETALX_MAIL_TLS``
- **Default:** ``False``

``ssl``
~~~~~~~

- Should SSL be used when sending mail? Only one of TLS and SSL may be used.
- **Environment variable:** ``PRETALX_MAIL_SSL``
- **Default:** ``True``
