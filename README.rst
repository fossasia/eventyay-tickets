eventyay-tickets
======

.. image:: https://codecov.io/gh/fossasia/eventyay-tickets/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/pretix/pretix

Project status & release cycle
------------------------------

Welcome to the **Eventyay** project! The ticketing component of the system provides options for **ticket sales and event-related items** such as T-shirts. Eventyay has been in development since **2014** and is based on a fork of **Pretix**.

Support
-------

This project is **free and open-source software**. Professional support is available to customers of the **hosted Eventyay service** or **Eventyay enterprise offerings**. If you are interested in commercial support, hosting services, or supporting this project financially, please go to `eventyay.com`.

Contributing
------------

Please look through our issues and start contributing.

Docker-based Setup (Temporary)
------------------------------
Currently, the non-Docker setup is broken. Until it is fixed, please use the Docker-based setup described below.

Install Docker (if not installed)
---------------------------------
- `Download Docker Desktop <https://www.docker.com/products/docker-desktop/>`_ and install it on your system.
- Ensure Docker is running by checking the version:

.. code-block:: sh

   docker --version

Clone and set up Eventyay-Docker
---------------------------------
Eventyay-Tickets runs inside **Eventyay-Docker**, so you need to set that up as well:

.. code-block:: sh

   cd ..  # Go back to the parent directory
   git clone https://github.com/fossasia/eventyay-docker.git
   cd eventyay-docker

Modify Hosts File (if needed)
-----------------------------
In some cases, you may need to modify the hosts file, but the development environment should work with `localhost`. This will be fixed in the future.

If required, add the following lines to your **/etc/hosts** file (Linux/macOS) or `C:\Windows\System32\drivers\etc\hosts` (Windows):

.. code-block:: 

   127.0.0.1       app.eventyay.com
   127.0.0.1       video.eventyay.com

Start Docker containers
-----------------------
Run:

.. code-block:: sh

   docker compose -f docker-compose.yml up -d

This explicitly specifies the compose file to ensure the correct services start.

Access the Running Application
------------------------------
- **Tickets App**: `http://app.eventyay.com`
- **Admin Panel**: `http://app.eventyay.com/control`

Find and edit frontend files
----------------------------
- **HTML Templates**: Located in `presale/templates/pretixpresale/`
- **CSS & JS Files**: Located in `presale/static/pretixpresale/`

After making changes, restart the service with:

.. code-block:: sh

   docker compose restart ticket

Create a Pull Request
----------------------
Once you're happy with your changes:

.. code-block:: sh

   git add .
   git commit -m "Updated documentation for setting up Eventyay-Tickets"
   git push origin YOUR_BRANCH_NAME

Then, go to GitHub and create a **Pull Request**!

License
-------

The code in this repository is published under the terms of the **Apache 2 License**.
See the LICENSE file for the complete license text.

This project is maintained by **FOSSASIA**. See the AUTHORS file for a list of all the awesome contributors of this project.

.. _installation guide: https://docs.eventyay.com/en/latest/admin/installation/index.html
.. _eventyay.com: https://eventyay.com
.. _blog: https://blog.eventyay.com

