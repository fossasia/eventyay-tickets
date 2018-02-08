.. _`administator-index`:

Administrator documentation
===========================

You want to install pretalx on your own server? That's great! We have two ways
of installation documented: installation via Docker, and installation via pip.
Both only document an uncomplicated setup without going into details on
performance tuning, alternate caching backends, etc. – if you have questions
regarding those areas, don't hesitate to ask.  (Alternatively, play around and
send us documentation pull requests!)

The pip installation is currently better supported since we have more
experience with pip, and are using pip based installations in production
ourselves. If you run into problems with the docker-based setup, we might take
longer to find a solution.
We also provide an `ansible role`_ compatible with our pip setup.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation_pip
   installation_docker
   configure


.. _ansible role: https://github.com/pretalx/ansible-pretalx
