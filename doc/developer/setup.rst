.. _`devsetup`:

The development setup
=====================

To contribute to pretalx, it's useful to run pretalx locally on your device so you can test your
changes. First of all, you need install some packages on your operating system:

If you want to install pretalx on a server for actual usage, go to the :ref:`administrator-index`
instead.

* git
* Python 3.6(!) or newer
* A recent version of pip
* gettext (Debian package: ``gettext``)
* tox as your development environment

If your operating system does not provide Python 3.6 or newer, you might need
to `compile it yourself`_ or install it from the `unstable` or `experimental`
repositories.

Some Python dependencies might also need a compiler during installation, the Debian package
``build-essential`` or something similar should suffice.

If you are working on Ubuntu or Debian, we strongly recommend upgrading your pip and setuptools
installation inside the virtual environment, otherwise some of the dependencies might fail::

    sudo pip3 install -U pip setuptools wheel

If ``tox`` is not available in your distribution's repositories, you can install it via pip::

    sudo pip3 install tox

Get a copy of the source code
-----------------------------
You can clone our git repository::

    git clone https://github.com/pretalx/pretalx.git
    cd pretalx/


Working with the code
---------------------

First up, check that ``tox`` is installed and working as expected::

    $ tox --listenvs
    dev
    lint
    tests-mysql-codecov
    tests-postgres-codecov
    tests-sqlite-codecov
    installation
    docs
    docs-linkcheck
    docs-autobuild

Then, create the local database::

    tox -e dev manage.py migrate
    tox -e dev -- manage.py collectstatic --noinput

To be able to log in, you should also create an admin user, organiser and team by running::

    tox -e dev manage.py init

Additionally, if you want to get started with an event right away, run the ``create_test_event`` command::


    tox -e dev manage.py create_test_event

This command will create a test event for you, with a set of test submissions,
and speakers, and the like. You will need to install the ``freezegun`` and
``Faker`` libraries.

With the ``--stage`` flag, you can determine which stage the event in question
should be in. The available choices are ``cfp`` (CfP still open, plenty of
submissions, but no reviews), ``review`` (submissions have been reviewed and
accepted/rejected), ``schedule`` (there is a schedule and the event is
currently running), and ``over``. ``schedule`` is the default value.

If you want to see pretalx in a different language than English, you have to compile our language
files::

    tox -e dev manage.py compilemessages

If you need to test more complicated features, you should probably look into the
:doc:`setup</administrator/installation>` documentation to find the bits and pieces you
want to add to your development setup.

Run the development server
^^^^^^^^^^^^^^^^^^^^^^^^^^
To run the local development server, execute::

    tox -e dev

Now point your browser to http://localhost:8000/orga/ – You should be able to log in and play
around!

Please note that if you want to add more flags to the development server, you'll have to call
the ``runserver`` command explicitly, which is otherwise the default. For example, this command
would run the development server on port ``5000`` instead of ``8000``::

    tox -e dev -- -m pretalx runserver localhost:5000

.. _`checksandtests`:

Code checks and unit tests
^^^^^^^^^^^^^^^^^^^^^^^^^^
Before you check in your code into git, always run the static checkers and unit tests::

    tox -e lint
    tox -e tests-sqlite

.. note:: If you have more than one CPU core and want to speed up the test suite, you can run
          ``tox -e dev -- -m pytest -n NUM`` with ``NUM`` being the number of threads you want to use.

If you edit a stylesheet ``.scss`` file, please run ``sass-convert -i path/to/file.scss``
afterwards to format that file.

Working with mails
^^^^^^^^^^^^^^^^^^

If you want to test emails in your development setup, we recommend starting
Python's debugging SMTP server in a separate shell and configuring pretalx to
use it. The debugging SMTP server will print every email to its stdout.

Add this to your ``src/pretalx.cfg``::

    [mail]
    port = 1025

Then execute ``python -m smtpd -n -c DebuggingServer localhost:1025``.

Working with translations
^^^^^^^^^^^^^^^^^^^^^^^^^
If you want to translate new strings that are not yet known to the translation system, you can use
the following command to scan the source code for strings we want to translate and update the
``*.po`` files accordingly::

    tox -e dev manage.py makemessages

To actually see pretalx in your language, you have to compile the ``*.po`` files to their optimised
binary ``*.mo`` counterparts::

    tox -e dev manage.py compilemessages

pretalx by default supports events in English, German, or French, or all three. To translate
pretalx to a new language, add the language code and natural name to the ``LANGUAGES`` variable in
the ``settings.py``. Depending on the completeness of your changes, and your commitment to maintain
them in the future, we can talk about merging them into core.


Working with the documentation
------------------------------

To build the documentation, run the following command::

    tox -e docs

You will now find the generated documentation in the ``doc/_build/html/`` subdirectory.
If you find yourself working with the documentation more than a little, give the ``autobuild``
functionality a try::

    tox -e docs-autobuild

Then, go to http://localhost:8081 for a version of the documentation that
automatically re-builds when you save a changed source file.
Please note that changes in the static files (stylesheets and JavaScript) will only be reflected
after a restart.

.. _compile it yourself: https://unix.stackexchange.com/a/332658/2013
