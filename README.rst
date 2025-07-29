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

- Python 3.5 or newer
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

      git clone https://github.com/Sak1012/eventyay-tickets.git

2. **Create and activate a virtual environment**:

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate

3. **Install and update pip and setuptools**:

   .. code-block:: bash

      pip3 install -U pip setuptools

4. **Enter the project directory**:

   .. code-block:: bash

      cd eventyay-tickets

5. **Switch to the `enext` branch**:

   .. code-block:: bash

      git switch enext

6. **Enter the unified Eventyay directory**:

   .. code-block:: bash

      cd eventyay

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


Support
-------

This project is **free and open-source software**. Professional support is available to customers of the **hosted Eventyay service** or **Eventyay enterprise offerings**. If you are interested in commercial support, hosting services, or supporting this project financially, please go to `eventyay.com`.

Contributing
------------

Please look through our issues and start contributing.

Setting Up Eventyay-Tickets
---------------------------

Eventyay-Tickets requires a Docker-based setup. Please follow the detailed instructions in the `development setup guide <https://github.com/fossasia/eventyay-docker/blob/main/README.development.md>`_ in the eventyay-docker repository.

License
-------

The code in this repository is published under the terms of the **Apache 2 License**.
See the LICENSE file for the complete license text.

This project is maintained by **FOSSASIA**. See the AUTHORS file for a list of all the awesome contributors of this project.

.. _installation guide: https://docs.eventyay.com/en/latest/admin/installation/index.html
.. _eventyay.com: https://eventyay.com
.. _blog: https://blog.eventyay.com


