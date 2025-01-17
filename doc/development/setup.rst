.. _`devsetup`:

Development setup
=================

This tutorial helps you to get started hacking with pretix on your own computer. You need this to
be able to contribute to pretix, but it might also be helpful if you want to write your own plugins.
If you want to install pretix on a server for actual usage, go to the :ref:`admindocs` instead.

Obtain a copy of the source code
--------------------------------
You can just clone our git repository:

.. code-block:: console

  $ git clone https://github.com/fossasia/eventyay-tickets.git
  $ cd eventyay-tickets/

External Dependencies
---------------------
Your should install the following on your system:

* Python 3.11 or newer
* ``pip`` for Python 3 (Debian package: ``python3-pip``)
* ``python-dev`` for Python 3 (Debian package: ``python3-dev``)
* On Debian/Ubuntu: ``python-venv`` for Python 3 (Debian package: ``python3-venv``)
* ``libffi`` (Debian package: ``libffi-dev``)
* ``libssl`` (Debian package: ``libssl-dev``)
* ``libxml2`` (Debian package ``libxml2-dev``)
* ``libxslt`` (Debian package ``libxslt1-dev``)
* ``libenchant1c2a`` (Debian package ``libenchant1c2a`` or ``libenchant2-2``)
* ``msgfmt`` (Debian package ``gettext``)
* ``freetype`` (Debian package ``libfreetype-dev``)
* ``git``
* for pillow: ``libjpeg`` (Debian Package ``libjpeg-dev``)

Your local python environment
-----------------------------

Install `uv`_ the Python package manager.

Please execute ``python -V`` or ``python3 -V`` to make sure you have Python 3.11
(or newer) installed. Also make sure you have pip for Python 3 installed, you can
execute ``pip3 -V`` to check.

Use `uv` to create a virtual environment for our project and install all dependencies:

.. code-block:: console

  $ uv sync --all-groups --no-install-project

Activate your virtual environment (`uv` creates virtual environment in _.venv_ directory):

.. code-block:: console

  $ source .venv/bin/activate

`uv` automatically creates virtual environment in _.venv_ directory.
If you want to create virtual environment outside the project directory, you can do so with
a different tool and tell `uv` to repspect the activated virtual environment by setting the
`UV_PROJECT_ENVIRONMENT` environment variable.

For Bash and Zsh:

.. code-block:: console

  $ export UV_PROJECT_ENVIRONMENT=$VIRTUAL_ENV

For Fish:

.. code-block:: console

  $ set -x UV_PROJECT_ENVIRONMENT $VIRTUAL_ENV

Working with the code
---------------------

You need to copy the SCSS files from the source folder to the STATIC_ROOT directory:

.. code-block:: console

  $ cd src/
  $ python manage.py collectstatic --no-input

Then, create the local database::

  python manage.py migrate

A first user with username ``admin@localhost`` and password ``admin`` will be automatically
created.

You will also need to install a few JavaScript dependencies::

  make npminstall

If you want to see pretix in a different language than English, you have to compile our language
files::

  make localecompile

Run the development server
^^^^^^^^^^^^^^^^^^^^^^^^^^
To run the local development webserver, execute::

    python manage.py runserver

and head to http://localhost:8000/

As we did not implement an overall front page yet, you need to go directly to
http://localhost:8000/control/ for the admin view.

.. note:: If you want the development server to listen on a different interface or
          port (for example because you develop on `pretixdroid`_), you can check
          `Django's documentation`_ for more options.

.. _`checksandtests`:

Code checks and unit tests
^^^^^^^^^^^^^^^^^^^^^^^^^^
Before you check in your code into git, always run static checkers and linters. If any of these commands fail,
your pull request will not be merged into pretix. If you have trouble figuring out *why* they fail, create your
pull request nevertheless and ask us for help, we are happy to assist you.

Execute the following commands to check for code style errors

.. code-block:: console

  $ ruff check .
  $ python manage.py check

Execute the following command to run pretix' test suite (might take a couple of minutes):

.. code-block:: console

  $ pytest

.. note:: If you have multiple CPU cores and want to speed up the test suite, you can install the python
          package ``pytest-xdist`` using ``pip3 install pytest-xdist`` and then run ``py.test -n NUM`` with
          ``NUM`` being the number of threads you want to use.

It is a good idea to install a Git pre-commit hook that runs these checks before you commit. You can do this:

.. code-block:: console

  $ pre-commit install

This keeps you from accidentally creating commits violating the style guide.

Working with mails
^^^^^^^^^^^^^^^^^^
If you want to test anything regarding emails in your development setup, we recommend
starting Python's debugging SMTP server in a separate shell and configuring pretix to use it.
Every email will then be printed to the debugging SMTP server's stdout.

Add this to your ``src/pretix.cfg``::

    [mail]
    port = 1025

Then execute ``python -m smtpd -n -c DebuggingServer localhost:1025``.

Working with translations
^^^^^^^^^^^^^^^^^^^^^^^^^
If you want to translate new strings that are not yet known to the translation system,
you can use the following command to scan the source code for strings to be translated
and update the ``*.po`` files accordingly::

    make localegen

However, most of the time you don't need to care about this. Just create your pull request
with functionality and English strings only, and we'll push the new translation strings
to our translation platform after the merge.

To actually see pretix in your language, you have to compile the ``*.po`` files to their
optimized binary ``*.mo`` counterparts::

    make localecompile


Working with the documentation
------------------------------

First, you should install the requirements necessary for building the documentation.

To build the documentation, run the following command from the ``doc/`` directory::

    make html

You will now find the generated documentation in the ``doc/_build/html/`` subdirectory. If you work
with the documentation a lot, you might find it useful to use sphinx-autobuild::

    pip3 install sphinx-autobuild
    sphinx-autobuild . _build/html -p 8081

Then, go to http://localhost:8081 for a version of the documentation that automatically re-builds
whenever you change a source file.

.. _Django's documentation: https://docs.djangoproject.com/en/5.1/ref/django-admin/#runserver
.. _uv: https://docs.astral.sh/uv/
