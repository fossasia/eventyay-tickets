.. _`devsetup`:

The development setup
=====================

To contribute to pretalx, it’s useful to run pretalx locally on your device so you can test your
changes. First of all, you need install some packages on your operating system:

If you want to install pretalx on a server for actual usage, go to the :ref:`administrator-index`
instead.

External dependencies
---------------------

Please make sure you have the following dependencies installed:

+----------------------------------+------------------+
| Tool                             | Debian package   |
+==================================+==================+
| Python 3.11(!) or newer          |                  |
+----------------------------------+------------------+
| pip for Python 3                 | ``python3-pip``  |
+----------------------------------+------------------+
| ``python-dev`` for Python 3      | ``python3-dev``  |
+----------------------------------+------------------+
| ``python-venv``, if not included | ``python3-venv`` |
+----------------------------------+------------------+
| libffi                           | ``libffi-dev``   |
+----------------------------------+------------------+
| gettext                          | ``gettext``      |
+----------------------------------+------------------+
| git                              | ``git``          |
+----------------------------------+------------------+
| uv                               |      N/A         |
+----------------------------------+------------------+
| `just`_ (optional)               | ``just``         |
+----------------------------------+------------------+

Some Python dependencies might also need a compiler during installation, the Debian package
``build-essential`` or something similar should suffice.

The ``uv`` tool is installed from https://docs.astral.sh/uv/.


Local Python environment
------------------------

Please execute ``python -V`` or ``python3 -V`` to make sure you have Python 3.11
(or newer) installed. Also make sure you have pip for Python 3 installed, by
running ``pip3 -V``.


Get a copy of the source code
-----------------------------
You can clone our git repository::

    git clone https://github.com/pretalx/pretalx.git
    cd pretalx/


Working with the code
---------------------

First up, install all the main application dependencies::

    uv sync

`uv` will create a virtual environment in the *.venv* folder. You can activate it with::

    source .venv/bin/activate

You should now see a *(.venv)* prepended to your shell prompt.

When working with `pretalx`, you need to use commands installed in this virtual environment, so you always have to activate it.
Other than explicitly activating, you can invoke the commands indirectly via `uv run`. For example:

.. code-block:: shell

    # With uv run
    $ uv run src/manage.py runserver
    # To run a module, equivalent to `python -m module`
    $ uv run -m module
    # To run a binary
    $ uv run djhtml
    # Without uv run
    $ source .venv/bin/activate
    (.venv)$ cd src
    (.venv)$ ./manage.py runserver

Next, you will have to copy the static files from the source folder to the
STATIC_ROOT directory, and create the local database::

    (.venv)$ cd src
    (.venv)$ python manage.py collectstatic --noinput
    (.venv)$ python manage.py migrate

To be able to log in, you should also create an admin user, organiser and team by running::

    (.venv)$ python manage.py init

Additionally, if you want to get started with an event right away, run the ``create_test_event`` command::

    (.venv)$ python manage.py create_test_event

This command will create a test event for you, with a set of test submissions,
and speakers, and the like.  With the ``--stage`` flag, you can determine which
stage the event in question should be in. The available choices are ``cfp``
(CfP still open, plenty of submissions, but no reviews), ``review``
(submissions have been reviewed and accepted/rejected), ``schedule`` (there is
a schedule and the event is currently running), and ``over``. ``schedule`` is
the default value.

If you want to see pretalx in a different language than English, you have to compile our language
files::

    (.venv)$ python manage.py compilemessages

If you need to test more complicated features, you should probably look into the
:doc:`setup</administrator/installation>` documentation to find the bits and pieces you
want to add to your development setup.

Run the development server
^^^^^^^^^^^^^^^^^^^^^^^^^^
To run the local development server, execute::

    (.venv)$ python manage.py runserver

Now point your browser to http://127.0.0.1:8000/orga/ – You should be able to log in and use
all sites except those that use big custom JavaScript components, like the schedule editor.
In order to use those, you have two options – in any case, you will need to have ``node`` and
``npm`` installed on your system.

If you just need to use the JavaScript component, but don’t need to change it,
compile the JavaScript files::

    (.venv)$ python manage.py rebuild --npm-install

If you want to change the JavaScript code, you can run the following command, which combines
the Python and the JavaScript development servers::

    (.venv)$ python manage.py devserver

.. _`checksandtests`:

Code checks and unit tests
^^^^^^^^^^^^^^^^^^^^^^^^^^
Before you check in your code into git, always run the static linters and style checkers::

    (.venv)$ djhtml -t 2 src

Once you’re done with those, run the tests::

    (.venv)$ python -m pytest tests/

Pytest, our test framework, has a lot of useful options, like ``--lf`` to repeat only failing
tests, ``-k something`` to run only tests called ``*something*``, and ``-x`` to stop on the
first breaking test.

.. note:: If you have more than one CPU core and want to speed up the test suite, you can run
          ``python -m pytest -n NUM`` with ``NUM`` being the number of threads you want to use.

If you edit a stylesheet ``.scss`` file, please run ``sass-convert -i path/to/file.scss``
afterwards to format that file.

.. tip::

    Some long commands are put in *justfile* to let you run them with a shorter command.
    For example, you can run ``just djhtml`` instead of ``djhtml -t 2 src``.

    It is better that you use a modern shell (like `fish`_) because it can give autocomplete
    for the ``just`` command based on recipes defined in *justfile*.

Working with mails
^^^^^^^^^^^^^^^^^^

When running in development mode, Pretalx uses Django’s console email backend.
This means the development server will print any emails to its stdout, instead
of sending them via SMTP.

If you want to test sending event emails via a custom SMTP server, we recommend
starting Python’s debugging SMTP server in a separate shell::

    python -m smtpd -n -c DebuggingServer localhost:1025

You can use this server by specifying host ``localhost`` and port ``1025`` in
the event email settings.

.. _`developer-translations`:

Working with translations
^^^^^^^^^^^^^^^^^^^^^^^^^
If you want to translate new strings that are not yet known to the translation system, you will
first include them in the ``.po`` files. As we share translations between both the JavaScript
frontend and the Python backend, you’ll need to install the frontend dependencies first::

    (.venv)$ cd src/pretalx/frontend/schedule-editor
    (.venv)$ npm ci

Then, use the following command to scan the source code for strings we want to
translate and update the ``*.po`` files accordingly::

    (.venv)$ python manage.py makemessages --keep-pot --all

To actually see pretalx in your language, you have to compile the ``*.po`` files to their optimised
binary ``*.mo`` counterparts::

    (.venv)$ python manage.py compilemessages

pretalx by default supports events in English, German, or French, or all three. To translate
pretalx to a new language, add the language code and natural name to the ``LANGUAGES`` variable in
the ``settings.py``. Depending on the completeness of your changes, and your commitment to maintain
them in the future, we can talk about merging them into core.


Working with the documentation
------------------------------

To build the documentation, you will have to install the documentation dependencies. Go to the root
directory of your git repository, and then run::

    (.venv)$ pip install --upgrade-strategy eager -Ur doc/requirements.txt

Then, go to the ``doc`` directory and run ``make html`` to build the documentation::

    (.venv)$ make html

You will now find the generated documentation in the ``doc/_build/html/`` subdirectory.
If you find yourself working with the documentation more than a little, give the ``autobuild``
functionality a try::

    (.venv)$ sphinx-autobuild . _build/html --port 8001

Then, go to http://localhost:8081 for a version of the documentation that
automatically re-builds when you save a changed source file.
Please note that changes in the static files (stylesheets and JavaScript) will only be reflected
after a restart.


.. _just: https://just.systems/
.. _fish: https://fishshell.com/
