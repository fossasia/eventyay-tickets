Management commands
===================

pretalx comes with a range of helpful management commands that you can execute
from the command line. Assuming you are in the same environment you installed
pretalx in, for example a certain user or a virtual environment, you'll execute
commands using Python::

  python -m pretalx <command> [<flags>] [<options>]

Database commands
-----------------

``python -m pretalx migrate``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``migrate`` command updates the database tables to conform to what pretalx
expects. It should be executed once upon installation and then on every update.
As ``migrate`` touches the database, you should have a backup of the state
before the command run, even though it should be non-destructive, and is
wrapped in transactions. Running ``migrate`` if nothing is to be done will
result in no modification to the database and a helpful output.

If migrations touch upon large populated tables, they may run for some time.
The release notes will include a warning if a potentially long-running
migration is included.

``python -m pretalx showmigrations``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you're debugging what state your database is in, the ``showmigrations``
command will show you which migrations have been applied. It may be useful
debug output to include in bug reports concerning database problems.

Debug commands
--------------

``python -m pretalx shell`` or ``python -m pretalx shell_plus``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can use the ``shell`` command to open a python shell with all the
configuration and the environment that pretalx runs with, so that you can
import pretalx modules.  If you install the ``django_extensions`` and
``ipython`` packages, you can also choose to execute the ``shell_plus`` command
instead, which will give you a shell with tab completion, and will initially
import the classes and methods you will probably need.

``python -m pretalx print_settings``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If other debugging fails, install the ``django_extensions`` package and run
``print_settings`` to receive full settings output – be careful, this will
contain passwords, so you should sanitise it before pasting it anywhere.

If you don't want to install an additional library, you can run these commands
instead::

    python -m pretalx shell
    >>> from django.conf import settings
    >>> from pprint import pprint
    >>> pprint(settings.__dict__)

The warning about included passwords and secrets in the output goes for this
version as well.

Core pretalx commands
---------------------

``python -m pretalx rebuild``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``rebuild`` command regenerates all static files. With the ``--clear``
flag, it deletes all existing compiled static files and compiles everything
from scratch. Should be run after every upgrade.

``python -m pretalx init``
~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``init`` command allows you to create a superuser and an organiser, to give
you all the tools to start configuring pretalx in the web interface. Should be
run only once in the beginning. You can safely abort the command at any time,
and it will not write anything to the database until you've finished
successfully.

``python -m pretalx createsuperuser``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you need an additional user after generating your initial administration user,
use ``createsuperuser``. Please note that superusers have access to all areas
of all events.

``python -m pretalx runperiodic``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``runperiodic`` command should be run by a cronjob in regular intervals, but
you can also trigger it manually if you think that something went wrong with
the regular execution.

``python -m pretalx export_schedule_html``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This command requires an event slug as an argument, and you can optionally
provide the ``--zip`` flag to produce a zip archive instead of a directory
structure. The command will print the location of the HTML export upon
successful exit and will exit with an error code otherwise.

``python -m pretalx import_schedule``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``import_schedule`` allows you to import a conference schedule xml file.
It takes the path to the xml file as its only argument. If no event with
the specified slug can be found in the database, a new event and a new organiser
will be created instead.

If an event with the correct slug was found, a new schedule version for that
event will be released based on the data of the schedule import.
