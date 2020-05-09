Management commands
===================

This reference describes management commands supported by the venueless server.
Generally, to run any command with our recommended Docker-based setup, you use a command line like this::

    $ docker exec -it venueless.service venueless <COMMAND> <ARGS>

We will not repeat the first part of that in the examples on this page. In the development setup, it looks like this
instead::

    $ docker-compose exec server python manage.py <COMMAND> <ARGS>

Database management
-------------------

``migrate``
"""""""""""

The ``migrate`` command updates the database tables to conform to what venueless expects.  As migrate touches the
database, you should have a backup of the state before the command run. Running migrate if venueless has no pending
database changes is harmless. It will result in no changes to the database.

If migrations touch upon large populated tables, they may run for some time. The release notes will include a warning
if an upgrade can trigger this behaviour.

.. note:: Currently, this command is run by default during server startup.

``showmigrations``
""""""""""""""""""

If you ran into trouble during ``migrate``, run ``showmigrations``. It will show you the current state of all venueless
migrations. It may be useful debug output to include in bug reports about database problems.

World management
----------------

``create_world``
""""""""""""""""

The interactive ``create_world`` command allows you to create an empty venueless world from scratch::

    > create_world
    Enter the internal ID for the new world (alphanumeric): myevent2020
    Enter the title for the new world: My Event 2020
    Enter the domain of the new world (e.g. myevent.example.org): venueless.mydomain.com
    World created.
    Default API keys: [{'issuer': 'any', 'audience': 'venueless', 'secret': 'zvB7hI28vbrI7KtsRnJ1TZBSN3DvYdoy9VoJGLI1ouHQP5VtRG3U6AgKJ9YOqKNU'}]

``clone_world``
""""""""""""""""

The interactive ``clone_world`` command allows you to create a venueless world while copying all settings and rooms
(but not users and user-generated content) from an existing one::

    > clone_world myevent2019
    Enter the internal ID for the new world (alphanumeric): myevent2020
    Enter the title for the new world: My Event 2020
    Enter the domain of the new world (e.g. myevent.example.org): venueless.mydomain.com
    World cloned.

``import_config``
"""""""""""""""""

The ``import`` command allows you to import a world configuration from a JSON file. It is mainly used during development
and testing to get started quickly. It takes a filename as the only argument. Note that the command looks for the file
*within* the Docker container::

    > import_config sample/worlds/sample.json


Connection management
---------------------

Connection management commands allow you to operate on the current user sessions on your system. They are useful during
system maintenance.

``connections list``
""""""""""""""""""""

Shows a list of connection labels and their estimated number of current connections. The estimated number might be
significantly higher than expected if connections where dropped without a cleanup, and old connection labels might
be lingering around for a couple of seconds. Connection labels are composed by the git commit ID of the venueless
build and the environment (read from the ``VENUELESS_ENVIRONMENT`` environment variable, ``unknown``) by default.
Sample output::

    > connections list
    label                              est. number of connections
    411b261.production                 3189

``connections drop``
""""""""""""""""""""

Tells the server to drop all connections, optionally filtered with a specific connection label. For example, you might
want to drop all connections still connected to an old version::

    > connections drop 411b261.*

The server will send out a message to all workers still having clients with this version to close these connections
immediately. If you do not want to drop all at once, you can pass a sleep interval, e.g. a number of milliseconds to
wait between every message that is sent out::

    > connections drop --interval 50 411b261.*

``connections force_reload``
""""""""""""""""""""""""""""

Tells the server to send a force-reload command to all connections, optionally filtered with a specific connection
label. For example, you might want to force-reload all connections still connected to an old version::

    > connections force_reload 411b261.*

This will not close the connections server-side, but instead instruct browsers to reload the application, e.g. to fetch
a new JavaScript application version.
If you do not want to reload all at once, you can pass a sleep interval, e.g. a number of milliseconds to
wait between every message that is sent out::

    > connections force_reload --interval 50 411b261.*

Debugging
---------

``shell``
"""""""""

The ``shell`` command opens a shell with the venueless configuration and environment. All database models and some more
useful modules will  be imported automatically.
