Management commands
===================

pretalx comes with commands that you can execute from the command line. Run
them in the same environment you installed pretalx in. If you followed the
installation guide, you should run them as the ``pretalx`` user, and either
use the ``/var/pretax/venv/bin/python`` executable, or activate the virtual
environment by running ``source /var/pretalx/venv/bin/activate``.

.. highlight:: console

All commands are run with the ``python -m pretalx`` prefix::

  python -m pretalx <command> [<flags>] [<options>]

You can add the ``--no-pretalx-information`` flag to any of these commands
to suppress the printing of the pretalx debug startup header.

Database commands
-----------------

``migrate``
~~~~~~~~~~~

The ``migrate`` command updates the database tables to conform to what pretalx
expects. Please execute it once upon installation and then on every update. As
``migrate`` touches the database, you should have a backup of the state before
the command run.
Running ``migrate`` if pretalx has no pending database changes  is harmless. It
will result in no changes to the database.

If migrations touch upon large populated tables, they may run for some time.
The :ref:`changelog` will include a warning if an upgrade can trigger this
behaviour.

``showmigrations``
~~~~~~~~~~~~~~~~~~

If you ran into trouble during ``migrate``, run ``showmigrations``. It will
show you the current state of all pretalx migrations. It may be useful debug
output to include in bug reports about database problems.

``clearsessions``
~~~~~~~~~~~~~~~~~

This command will remove old and unusable sessions from the database. We
recommend that you run it about once a month to keep your database at a
reasonable size.

Debug commands
--------------

``shell_scoped``
~~~~~~~~~~~~~~~~

The ``shell_scoped`` command opens a Python shell with the pretalx
configuration and environment. You can use it to import pretalx modules and
execute methods. For a better environment, install ``django_extensions`` and
``ipython``.

You’ll have to provide the event you want to interact with to provide proper
database isolation::

    $ python -m pretalx shell_scoped --event__slug=myevent

Alternatively, you can specify that you want to be able to access all events::

    $ python -m pretalx shell_scoped --override

``print_settings``
~~~~~~~~~~~~~~~~~~

If other debugging fails, install the ``django_extensions`` package. Run
``print_settings`` to receive full settings output. The output will contain
passwords, so sanitise it before pasting it anywhere.

.. highlight:: python

If you don’t want to install a library for debugging, you can run these
commands in the pretalx ``shell`` command::

    >>> from django.conf import settings
    >>> from pprint import pprint
    >>> pprint(settings.__dict__)

Core pretalx commands
---------------------

``rebuild``
~~~~~~~~~~~

The ``rebuild`` command regenerates all static files. With the ``--clear``
flag, it replaces all static files with ones compiled from scratch. Run this
command after every upgrade.

Run this command with ``--npm-install`` to install or update all frontend
dependencies. This option will automatically be used the first time when
pretalx detects that you don’t have a ``node_modules`` directory, but it’s your
responsibility to use it during updates. It’s not the default as running ``npm
install`` can take a long time.

``regenerate_css``
~~~~~~~~~~~~~~~~~~

The ``regenerate_css`` command regenerates only the custom CSS for events. It
only runs for events with a specified custom colour, or custom uploaded styles.
You can specify an event slug with ``--event``. If no event is specified, the
files for all relevant events will be rebuilt.

``init``
~~~~~~~~

The ``init`` command allows you to create a superuser and an organiser. It is
useful to give you all the tools to start configuring pretalx in the web
interface. Please run this command once in the beginning. You can abort the
command at any time, and it will not write anything to the database.

With the ``--noinput`` flag, this command will *not* prompt you interactively
on standard input, but will instead read from the environment. This is
especially useful for automating invocations of this command. For the first
phase (creation of a superuser), set the environment variables
``DJANGO_SUPERUSER_EMAIL`` and ``DJANGO_SUPERUSER_PASSWORD`` (`see also the
documentation of the non-interactive mode of the corresponding Django command
<https://docs.djangoproject.com/en/4.2/ref/django-admin/#createsuperuser>`_).
For the second phase (creation of an organiser), set the environment variables
``PRETALX_INIT_ORGANISER_NAME`` and ``PRETALX_INIT_ORGANISER_SLUG``.

``createsuperuser``
~~~~~~~~~~~~~~~~~~~

If you need more users after generating your initial administration user,
use ``createsuperuser``. Please note that superusers have access to all areas
of all events.

``runperiodic``
~~~~~~~~~~~~~~~

Please run the ``runperiodic`` command in regular intervals, e.g. every 5-10
minutes.

``export_schedule_html``
~~~~~~~~~~~~~~~~~~~~~~~~

This command requires an event slug as an argument. You can provide the
``--zip`` flag to produce a zip archive instead of a directory structure. The
command will print the location of the HTML export upon successful exit.

``create_test_event``
~~~~~~~~~~~~~~~~~~~~~

This command will create a test event for you, with a set of test submissions,
and speakers, and the like. You will need to install the ``freezegun`` and
``Faker`` libraries.

With the ``--stage`` flag, you can determine which stage the event in question
should be in. The available choices are ``cfp`` (CfP still open, plenty of
submissions, but no reviews), ``review`` (submissions have been reviewed and
accepted/rejected), ``schedule`` (there is a schedule and the event is
currently running), and ``over``. ``schedule`` is the default value.

The ``--slug`` flag allows you to specify the slug of the event to be created.
It defaults to ``democon``. Please only use alphanumerical characters and ``-``
in the slug, otherwise you won’t be able to see the event in the web interface.

``move_event``
~~~~~~~~~~~~~~

This command will move a given event (with the ``--event <event_slug>``
parameter) event. By default, the event start date will be set to the current
day, but you can configure any date using the ``--date 2021-12-26`` argument.

Data moved includes event start and end dates and the dates of all talks, both
current and historical. No new schedule versions will need to be created.

This command is intended to be used with demo or test events. If you move an
actual event like this, be prepared for some odd behaviour and please release a
new schedule version to make sure external tools can process the changes.

Development commands
--------------------

``makemessages``
~~~~~~~~~~~~~~~~

This command regenerates translation files. It should only be used during
pretalx development.

``makemigrations``
~~~~~~~~~~~~~~~~~~

This command generates new migration files for database changed. It should ONLY
be used during pretalx development, even if you are running a custom
installation, or if the console output of pretalx tells you to run it in case
of changes to database models.

``create_social_apps``
~~~~~~~~~~~~~~~~~~~~~~~
This command is used to create SocialApp entries for Eventyay-ticket Provider

``sync_customer_account``
~~~~~~~~~~~~~~~~~~~~~~~~~~~
This command is used to sync customer accounts from Eventyay Ticket
