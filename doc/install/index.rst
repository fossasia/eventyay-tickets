Installing pretalx
==================

That's great! We have two ways of installation documented: installation via
Docker, and manual installation. Both only document a simple development setup
without going into details on performance tuning, alternate caching backends,
etc. – if you have questions regarding those areas, don't hesitate to ask.
(Alternatively, play around and send us documentation pull requests!)

Head to the Docker installation section if you want things to just work™ out
of the box – if for some reason you cannot or don't want to use docker, check
the manual setup section – we also provide an `ansible role`_ compatible with
this method.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   simple_manual
   simple_docker
   configure


.. _ansible role: https://github.com/pretalx/ansible-pretalx
