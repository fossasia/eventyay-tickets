NGINX and URL Path Configuration for Eventyay-Tickets
=====================================================

This document outlines the NGINX and URL path setup for the ``eventyay-tickets`` project hosted at `https://github.com/fossasia/eventyay-tickets`. This Django project utilizes ``FORCE_SCRIPT_NAME`` to configure a base path, allowing the application to run on a specified sub-path within the domain.

Project Setup in Django
-----------------------

In ``eventyay-tickets``, the following settings are used to configure the base path for the application:

.. code-block:: python

    # Django Settings
    BASE_PATH = config.get('pretix', 'base_path', fallback='/tickets')
    FORCE_SCRIPT_NAME = BASE_PATH

- **BASE_PATH**: Retrieved from the ``pretix.cfg`` configuration file, which allows flexible configuration of the base URL path. By default, this is set to ``'/tickets'``.
- **FORCE_SCRIPT_NAME**: Uses the value from ``BASE_PATH``, setting ``/tickets`` as the base path for URL routing within Django.

This means that all URLs within Django are prefixed with ``/tickets``, allowing users to access ``eventyay-tickets`` via URLs like ``domain.com/tickets/``.

NGINX Configuration
-------------------

The following NGINX configuration serves the ``eventyay-tickets`` application along with other services such as ``talk`` and ``video``. The configuration is hosted on server.

Key Sections of NGINX Configuration
-----------------------------------

1. **Server Block for HTTPS**:
   This block listens on port ``443`` for HTTPS traffic.
   SSL certificates are configured here using Let's Encrypt for secure communication.

   .. code-block:: nginx

       server {
           server_name your-domain;
           listen 443 ssl;

           ssl_certificate /etc/../fullchain.pem;
           ssl_certificate_key /etc/../privkey.pem;
           include /etc/../options-ssl-nginx.conf;
           ssl_dhparam /etc/../ssl-dhparams.pem;
       }

2. **URL Path Configurations**:

   - **Root Location**:
     - Proxies requests from ``https://your-domain/`` to the backend on ``localhost:8455/common/``.

   - **/tickets**:
     - This location is for the ``eventyay-tickets`` application.
     - Requests to ``https://your-domain/tickets/`` are proxied to ``localhost:8455/``.

     .. code-block:: nginx

         location /tickets/ {
             proxy_pass http://localhost:8455/;
             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
             proxy_set_header X-Forwarded-Proto $scheme;
             proxy_set_header Host $host;
         }

   - **/talk** and **/video**:
     - These locations handle other components (``talk`` and ``video``) by proxying requests to their respective backend services on different ports.

3. **Custom Redirects**:
   - **/video/admin**:
     - Redirects requests from ``/video/admin/`` to the ``control`` panel at ``https://your-domain:8443/control``.

     .. code-block:: nginx

         location /video/admin/ {
             return 301 https://your-domain:8443/control;
         }

   - **/talk/static** and **/media**:
     - Routes static files for the ``talk`` component, setting up paths for ``/talk/media/`` and ``/media/`` to point to Docker volumes where media files are stored.

     .. code-block:: nginx

         location /talk/media/ {
             rewrite ^/talk/media/(.*)$ /media/$1 break;
             root /var/lib/docker/volumes/pretalx_pretalx-data/_data;
         }

4. **HTTP to HTTPS Redirection**:
   - Redirects all HTTP requests on port ``80`` to HTTPS, ensuring secure communication.

   .. code-block:: nginx

       server {
           listen 80;
           server_name your-domain;
           if ($host = your-domain) {
               return 301 https://$host$request_uri;
           }
           return 404;
       }

5. **Secondary HTTPS Server Block on Port 8443**:
   - A separate server block listens on port ``8443`` for HTTPS traffic and proxies requests to the backend service running on port ``8375``.

   .. code-block:: nginx

       server {
           listen 8443 ssl;
           server_name your-domain;

           ssl_certificate /etc/../fullchain.pem;
           ssl_certificate_key /etc/../privkey.pem;
           include /etc/../options-ssl-nginx.conf;
           ssl_dhparam /etc/../ssl-dhparams.pem;

           location / {
               proxy_pass http://localhost:8375/;
               proxy_http_version 1.1;
               proxy_set_header Upgrade $http_upgrade;
               proxy_set_header Connection "upgrade";
               proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
               proxy_set_header X-Forwarded-Proto https;
               proxy_set_header Host $http_host;
           }
       }

Accessing eventyay-tickets
--------------------------

With this setup:

- The URL for accessing the ``eventyay-tickets`` application control panel is ``https://your-domain/tickets/control``.
- NGINX routes requests to the correct backend ports based on path prefixes, ensuring that each application (tickets, talk, video) is isolated within its respective path.

Summary
-------

This configuration leverages ``FORCE_SCRIPT_NAME`` in Django to set ``/tickets`` as the base path, while NGINX routes requests to various services based on URL path prefixes. This setup provides a secure and organized way to access different components on the same domain.
