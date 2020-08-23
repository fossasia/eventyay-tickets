Development setup
=================

Installation
------------

A venueless installation currently contains four components:

* A frontend web application with our user interface

* A server application exposing our API

* A PostgreSQL database server

* A redis database server

While you can execute them all independently, our recommended development setup uses **docker-compose** to make sure
everyone works with the same setup and to make it easy to run all these components. So the only prerequisites for
development on your machine are:

* Docker
* docker-compose

To get started, you can use the following command to create the docker containers and start them up::

    docker-compose up --build

Our server application will now run on your computer on port 8375, and our web application on port 8880. Both of them
are configured to automatically restart whenever you change the code, so you can now pick your favorite text editor
and get started.

To make things more interesting, you should import a sample configuration with some basic event data::

    docker-compose exec server python manage.py import_config sample/worlds/sample.json

Then, you can visit http://localhost:8880/ in your browser to access the event as a guest user.


Running tests
-------------

Our server component comes with an extensive test suite. After you made some changes, you should give it a run and see
if everything still works::

    docker-compose exec server pytest

Code style
----------

For our server component, we enforce a specific code style to make things more consistent and diffs easier to read.
Any pull requests you send us will automatically be checked against these rules.

To check locally, it is convenient to have a local Python environment (such as a virtual environemnt) in which you
can install the dependencies of the server component::

	(venueless) $ cd server
	(venueless) $ pip install -r requirements.txt

To auto-format the code according to the code style and to check for linter issues, you can run the following
commands::

	(venueless) $ black venueless tests
	(venueless) $ isort -rc venueless tests
	(venueless) $ flake8 venueless tests

To automatically check before commits, add a script like the following to ``.git/hooks/pre-commit`` and apply ``chmod +x .git/hooks/pre-commit``::

	#!/bin/bash
	source ~/.virtualenvs/venueless/bin/activate
	cd server
	for file in $(git diff --cached --name-only | grep -E '\.py$' | grep -Ev "venueless/celery_app\.py|venueless/settings\.py")
	do
	  echo Scanning $file
	  git show ":$file" | black -q --check - || { echo "Black failed."; exit 1; } # we only want to lint the staged changes, not any un-staged changes
	  git show ":$file" | flake8 - --stdin-display-name="$file" || exit 1 # we only want to lint the staged changes, not any un-staged changes
	  git show ":$file" | isort -df --check-only - | grep ERROR && exit 1 || true
	done

