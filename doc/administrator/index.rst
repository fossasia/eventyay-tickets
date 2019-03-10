.. _`administrator-index`:

Administrator documentation
===========================

You want to install pretalx on your own server? That's great! We have 
documentation for a standard installation using pip in an unprivileged local
user account. If you want a more out-of-the-box way of running pretalx, head
over to our `docker-compose setup`_ (but note that the pip installation is by
far better tested and supported than the docker setup).

The following documents an uncomplicated setup without going into details on
performance tuning, alternate caching backends, and so on. – if you have
questions, don't hesitate to ask.  (Or you can play around and send us
documentation pull requests!)

We also provide an `ansible role`_ compatible with our pip setup.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   configure
   maintenance
   commands


.. _ansible role: https://github.com/pretalx/ansible-pretalx
.. _docker-compose setup: https://github.com/pretalx/pretalx-docker
