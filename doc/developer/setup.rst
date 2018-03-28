The development setup
=====================

To contribute to pretalx, it's useful to run pretalx locally on your device so you can test your
changes. First of all, you need install some packages on your operating system:

If you want to install pretalx on a server for actual usage, go to the :ref:`administrator-index` instead.

* git
* Python 3.6(!) or newer
* A recent version of pip
* gettext (Debian package: ``gettext``)

On Arch Linux, Python 3.6 is already in the default repositories::

    sudo pacman -S python python-pip gettext git

On Debian and Ubuntu, Python 3.6 is not yet in the repositories. You might need to `compile it
yourself`_ or install it from the `unstable` or `experimental` repositories.

Some Python dependencies might also need a compiler during installation, the Debian package
``build-essential`` or something similar should suffice.

Get a copy of the source code
-----------------------------
You can clone our git repository::

    git clone https://github.com/pretalx/pretalx.git
    cd pretalx/


Your local python environment
-----------------------------

Please execute ``python -V`` or ``python3.6 -V`` to make sure you have Python 3.6 (or newer)
installed. Also make sure you have pip for Python 3 installed, you can execute ``pip3 -V`` to check.
Then use Python's internal tools to create a virtual environment and activate it for your current
session::

    python3.6 -m venv env
    source env/bin/activate

You should now see a ``(env)`` prepended to your shell prompt. You have to do this in every shell
you use to work with pretalx (or configure your shell to do so automatically). If you are working on
Ubuntu or Debian, we strongly recommend upgrading your pip and setuptools installation inside the
virtual environment, otherwise some of the dependencies might fail::

    (env)$ pip3 install -U pip setuptools wheel


Working with the code
---------------------
The first thing you need are all the main application's dependencies::

    (env)$ cd src/
    (env)$ pip3 install -r requirements/production.txt -r requirements/dev.txt -r requirements/fancy.txt

Then, create the local database::

    (env)$ python manage.py migrate

To be able to log in, you should also create an admin user::

    (env)$ python manage.py init

If you want to see pretalx in a different language than English, you have to compile our language
files::

    (env)$ python manage.py compilemessages

If you need to test more complicated features, you should probably look into the
:doc:`manual setup</administrator/installation_pip>` documentation to find the bits and pieces you
want to add to your development setup.

Run the development server
^^^^^^^^^^^^^^^^^^^^^^^^^^
To run the local development server, execute::

    (env)$ python manage.py runserver

Now point your browser to http://localhost:8000/orga/ – You should be able to log in and play
around!

.. _`checksandtests`:

Code checks and unit tests
^^^^^^^^^^^^^^^^^^^^^^^^^^
Before you check in your code into git, always run the static checkers and unit tests::

    (env)$ pylama
    (env)$ isort -c -rc .
    (env)$ python manage.py check
    (env)$ py.test tests

.. note:: If you have more than one CPU core and want to speed up the test suite, you can run
          ``py.test -n NUM`` with ``NUM`` being the number of threads you want to use.

It's a good idea to put the style checks into your git hook ``.git/hooks/pre-commit``,
for example::

    #!/bin/sh
    set -e
    cd $GIT_DIR/../src
    source ../env/bin/activate
    pylama
    isort -c -rc .

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

    (env)$ python manage.py makemessages

To actually see pretalx in your language, you have to compile the ``*.po`` files to their optimized
binary ``*.mo`` counterparts::

    (env)$ python manage.py compilemessages


Working with the documentation
------------------------------
First, you should install the requirements necessary for building the documentation.  Make sure you
have your virtual python environment activated (see above). Then, install the packages by
executing::

    (env)$ cd doc/
    (env)$ pip3 install -r requirements.txt

To build the documentation, run the following command from the ``doc/`` directory::

    (env)$ make html

You will now find the generated documentation in the ``doc/_build/html/`` subdirectory.

.. _compile it yourself: https://unix.stackexchange.com/a/332658/2013
