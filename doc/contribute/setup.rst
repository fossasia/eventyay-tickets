The development setup
=====================

To contribute to pretalx, it's very useful to run pretalx locally on your device so you can test
your changes. First of all, you need install a few things on your operating system:

* git
* Python 3.6(!) or newer
* A recent version of pip
* gettext (Debian package: ``gettext``)

On Arch Linux, that's a simple::

    sudo pacman -S python python-pip gettext git

On Debian and Ubuntu, Python 3.6 is not yet in the repositories. You might need to `compile it yourself`_
or install it from the `unstable` or `experimental` repositories.

Some Python dependencies might also need a compiler during installation, the Debian package ``build-essential``
or something similar should suffice.

Obtain a copy of the source code
--------------------------------
You can just clone our git repository::

    git clone https://github.com/openeventstack/pretalx.git
    cd pretalx/


Your local python environment
-----------------------------

Please execute ``python -V`` or ``python3.6 -V`` to make sure you have Python 3.6
(or newer) installed. Also make sure you have pip for Python 3 installed, you can
execute ``pip3 -V`` to check. Then use Python's internal tools to create a virtual
environment and activate it for your current session::

    python3.6 -m venv env
    source env/bin/activate

You should now see a ``(env)`` prepended to your shell prompt. You have to do this
in every shell you use to work with pretalx (or configure your shell to do so
automatically). If you are working on Ubuntu or Debian, we strongly recommend upgrading
your pip and setuptools installation inside the virtual environment, otherwise some of
the dependencies might fail::

    pip3 install -U pip setuptools wheel


Working with the code
---------------------
The first thing you need are all the main application's dependencies::

    cd src/
    pip3 install -r requirements/production.txt -r requirements/dev.txt -r requirements/fancy.txt

Then, create the local database::

    python manage.py migrate

To be able to log in, you should also create an admin user::

    python manage.py createsuperuser

If you want to see pretalx in a different language than English, you have to compile our language
files::

    python manage.py compilemessages

Run the development server
^^^^^^^^^^^^^^^^^^^^^^^^^^
To run the local development webserver, execute::

    python manage.py runserver

and point your browser to http://localhost:8000/orga/ – You should be able to log in and play around!

.. _`checksandtests`:

Code checks and unit tests
^^^^^^^^^^^^^^^^^^^^^^^^^^
Before you check in your code into git, always run the static checkers and unit tests::

    pylama
    isort -c -rc .
    python manage.py check
    py.test tests

.. note:: If you have multiple CPU cores and want to speed up the test suite, you can run
          ``py.test -n NUM`` with ``NUM`` being the number of threads you want to use.

It is a good idea to put the style checks into your git hook ``.git/hooks/pre-commit``,
for example::

    #!/bin/sh
    cd $GIT_DIR/../src
    source ../env/bin/activate
    pylama
    isort -c -rc .

Working with translations
^^^^^^^^^^^^^^^^^^^^^^^^^
If you want to translate new strings that are not yet known to the translation system,
you can use the following command to scan the source code for strings to be translated
and update the ``*.po`` files accordingly::

    python manage.py makemessages

To actually see pretix in your language, you have to compile the ``*.po`` files to their
optimized binary ``*.mo`` counterparts::

    python manage.py compilemessages


Working with the documentation
------------------------------
First, you should install the requirements necessary for building the documentation.
Make sure you have your virtual python environment activated (see above). Then, install the
packages by executing::

    cd doc/
    pip3 install -r requirements.txt

To build the documentation, run the following command from the ``doc/`` directory::

    make html

You will now find the generated documentation in the ``doc/_build/html/`` subdirectory.

.. _compile it yourself: https://unix.stackexchange.com/a/332658/2013
