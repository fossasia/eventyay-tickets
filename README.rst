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

### Setting Up Eventyay-Tickets Locally
Since **Eventyay-Tickets** is a backend-driven project, you need **Docker** to run it properly. If you already have Docker installed, skip to the next step.

1. **Install Docker (If Not Installed)**
   - [Download Docker Desktop](https://www.docker.com/products/docker-desktop/) and install it on your system.
   - Ensure Docker is running by checking the version:
     ```sh
     docker --version
     ```

2. **Clone & Set Up Eventyay-Docker**
   Eventyay-Tickets runs inside **Eventyay-Docker**, so you need to set that up as well:
   ```sh
   cd ..  # Go back to the parent directory
   git clone https://github.com/fossasia/eventyay-docker.git
   cd eventyay-docker
   ```

3. **Modify Hosts File (Important!)**
   Add the following lines to your **/etc/hosts** file (Linux/macOS) or `C:\Windows\System32\drivers\etc\hosts` (Windows):
   ```
   127.0.0.1       app.eventyay.com
   127.0.0.1       video.eventyay.com
   ```

4. **Start Docker Containers**
   Run:
   ```sh
   docker compose up -d
   ```
   This will pull the required images and set up all services.

5. **Access the Running Application**
   - **Tickets App**: `http://app.eventyay.com`
   - **Admin Panel**: `http://app.eventyay.com/control`

6. **Find & Edit Frontend Files**
   - **HTML Templates**: Located in `presale/templates/pretixpresale/`
   - **CSS & JS Files**: Located in `presale/static/pretixpresale/`

   After making changes, restart the service with:
   ```sh
   docker compose restart ticket
   ```

7. **Create a Pull Request**
   Once you're happy with your changes:
   ```sh
   git add .
   git commit -m "Updated documentation for setting up Eventyay-Tickets"
   git push origin YOUR_BRANCH_NAME
   ```
   Then, go to GitHub and create a **Pull Request**!

License
-------

The code in this repository is published under the terms of the **Apache 2 License**.
See the LICENSE file for the complete license text.

This project is maintained by **FOSSASIA**. See the AUTHORS file for a list of all the awesome contributors of this project.

.. _installation guide: https://docs.eventyay.com/en/latest/admin/installation/index.html
.. _eventyay.com: https://eventyay.com
.. _blog: https://blog.eventyay.com


