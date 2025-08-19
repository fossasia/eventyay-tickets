eventyay-tickets (ENext)
======

.. image:: https://codecov.io/gh/fossasia/eventyay-tickets/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/pretix/pretix

Project status & release cycle
------------------------------

Welcome to the **Eventyay** project! The ticketing component of the system provides options for **ticket sales and event-related items** such as T-shirts. Eventyay has been in development since **2014**. Its ticketing component is based on a fork of **Pretix**.

ENext is the new and updated version of Eventyay with a unified codebase for the Tickets, Talk, and Videos components.

External Dependencies
---------------------

You should install the following dependencies on your system:

- Python 3.11 or newer
- ``pip`` for Python 3 (Debian package: ``python3-pip``)
- ``python-dev`` for Python 3 (Debian package: ``python3-dev``)
- On Debian/Ubuntu: ``python-venv`` for Python 3 (Debian package: ``python3-venv``)
- ``libffi`` (Debian package: ``libffi-dev``)
- ``libssl`` (Debian package: ``libssl-dev``)
- ``libxml2`` (Debian package: ``libxml2-dev``)
- ``libxslt`` (Debian package: ``libxslt1-dev``)
- ``libenchant1c2a`` (Debian package: ``libenchant1c2a`` or ``libenchant2-2``)
- ``msgfmt`` (Debian package: ``gettext``)
- ``freetype`` (Debian package: ``libfreetype-dev``)
- ``git``
- For Pillow: ``libjpeg`` (Debian package: ``libjpeg-dev``)

Getting Started
---------------

1. **Clone the repository**:

   .. code-block:: bash

      git clone https://github.com/fossasia/eventyay-tickets.git

2. **Enter the project directory**:

   .. code-block:: bash

      cd eventyay-tickets

3. **Create and activate a virtual environment**:

   Either use venv or pyenv to set up an environment and activate it.

   With venv you have to activate the environment everytime you start a new shell.

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate

   With pyenv you have to do the next only once, and can then forget. Whenever
   you are in the `eventyay-tickets` directory, the `enext-env` will be used.
   
   .. code-block:: bash
   
      pyenv virtualenv 3.11 enext-env
      pyenv local enext-env

4. **Install and update pip and setuptools**:

   .. code-block:: bash

      pip3 install -U pip setuptools


5. **Switch to the `enext` branch**:

   .. code-block:: bash

      git switch enext

6. **Enter the app directory**:

   .. code-block:: bash

      cd app

7. **Install required Python packages**:

   .. code-block:: bash

      pip install -r requirements.txt

8. **Initialize the database**:

   .. code-block:: bash

      python manage.py migrate

9. **Create a superuser account** (for accessing the admin panel):

   .. code-block:: bash

      python manage.py createsuperuser

10. **Run the development server**:

    .. code-block:: bash

       python manage.py runserver



Docker based development
------------------------

We assume your current working directory is the checkout of this repo.

1. **Create deployment/.env.dev**

   .. code-block:: bash

      cp deployment/env.dev-sample .env.dev

2. **Edit .env.dev**

   Only if necessary

3. **Make sure you don't have some old volumes hanging around**

   This is only necessary the first time, or if you have strange behaviour.
   This removes the database volume and triggers a complete reinitialization.
   After that, you have to run migrate and createsuperuser again!

   .. code-block:: bash

      docker volume rm eventyay_postgres_data_dev eventyay_static_volume

4. **Build and run the images**

   .. code-block:: bash

      docker compose up -d --build

5. **Create a superuser account** (for accessing the admin panel):

   This should be necessary only once, since the database is persisted 
   as docker volume. If you see strange behaviour, see the point 3.
   on how to reset.

   .. code-block:: bash

      docker exec -ti eventyay-next-web python manage.py createsuperuser

6. **Visit the site**

   Open `http://localhost:8000` in a browser.

6. **Checking the logs**

   .. code-block:: bash

      docker compose logs -f


7. **Shut down**

   To shut down the development docker deployment, run

   .. code-block:: bash

      docker compose down

The directory `app` is mounted into the docker, thus live editing is supported.


Deployment
----------

* copy all of the deployment directory onto the server as `/home/fossasia/enext`
* prepare the used volumes in docker-compose: one for static files and one for
  the postgres database. Create on the server:
        /home/fossasia/enext/data/static
        /home/fossasia/enext/data/postgres
  and
        chown 100:101 /home/fossasia/enext/data/static
* copy `env.prod-sample` to `.env` in `/home/fossasia/enext`, and edit it to your
  liking
* copy `nginx/enext-direct` to your system `/etc/nginx/sites-available`
  The file needs to be adjusted if the `enext` dir is NOT in `/home/fossasia`!
* Link the `enext-direct` file into `/etc/nginx/sites-enabled`
* Restart nginx
* Run
        docker compose up -d

Support
-------

This project is **free and open-source software**. Professional support is available to customers of the **hosted Eventyay service** or **Eventyay enterprise offerings**. If you are interested in commercial support, hosting services, or supporting this project financially, please go to `eventyay.com`.

Contributing
------------

Please look through our issues and start contributing.

License
-------

The code in this repository is published under the terms of the **Apache 2 License**.
See the LICENSE file for the complete license text.

This project is maintained by **FOSSASIA**. See the AUTHORS file for a list of all the awesome contributors of this project.

.. _installation guide: https://docs.eventyay.com/en/latest/admin/installation/index.html
.. _eventyay.com: https://eventyay.com
.. _blog: https://blog.eventyay.com


