.. highlight:: python
   :linenothreshold: 5

.. _`pluginsetup`:

Creating a plugin
=================

You can extend pretalx with custom Python code using the official plugin API.
Think of every plugin as an independent Django 'app' living in its own python
package installed like any other python module.

The communication between pretalx and the plugins happens using Django's
`signal dispatcher`_ feature. The core modules of pretalx expose signals which
you can read about on the next pages.

To create a new plugin, create a new python package which must be a valid
`Django app`_ and must contain plugin metadata, as described below.
You will need some boilerplate for every plugin to get started. To save your
time, we created a `cookiecutter`_ template that you can use like this::

   (env)$ pip install cookiecutter
   (env)$ cookiecutter https://github.com/pretalx/pretalx-plugin-cookiecutter

This will ask you some questions and then create a project folder for your plugin.

The following pages go into detail about the types of plugins
supported. While these instructions don't assume that you know a lot about
pretalx, they do assume that you have prior knowledge about Django (e.g. its
view layer, how its ORM works, etc.).

Plugin metadata
---------------

The plugin metadata lives inside a ``PretalxPluginMeta`` class inside your app's
configuration class. The metadata class must define the following attributes:

.. rst-class:: rest-resource-table

================== ==================== ===========================================================
Attribute          Type                 Description
================== ==================== ===========================================================
name               string               The human-readable name of your plugin
author             string               Your name
version            string               A human-readable version code of your plugin
description        string               A more verbose description of what your plugin does.
================== ==================== ===========================================================

A working example would be::

    from django.apps import AppConfig
    from django.utils.translation import ugettext_lazy as _


    class FacebookApp(AppConfig):
        name = 'pretalx_facebook'
        verbose_name = _("Facebook")

        class PretalxPluginMeta:
            name = _("Facebook")
            author = _("the pretalx team")
            version = '1.0.0'
            visible = True
            restricted = False
            description = _("This plugin allows you to post talks to facebook.")


    default_app_config = 'pretalx_facebook.FacebookApp'

Plugin registration
-------------------

Somehow, pretalx needs to know that your plugin exists at all. For this purpose, we
make use of the `entry point`_ feature of setuptools. To register a plugin that lives
in a separate python package, your ``setup.py`` should contain something like this::

    setup(
        args...,
        entry_points="""
    [pretalx.plugin]
    pretalx_paypal=pretalx_paypal:PretalxPluginMeta
    """
    )


This will automatically make pretalx discover this plugin as soon as you have
installed it e.g.  through ``pip``. During development, you can run ``python
setup.py develop`` inside your plugin source directory to make it discoverable.

Signals
-------

pretalx defines signals which your plugin can listen for. We will go into the
details of the different signals in the following pages. We suggest that you
put your signal receivers into a ``signals`` submodule of your plugin. You
should extend your ``AppConfig`` (see above) by the following method to make
your receivers available::

    class PaypalApp(AppConfig):
        …

        def ready(self):
            from . import signals  # noqa

You can optionally specify code that you want to execute when the organiser
activates your plugin for an event in the ``installed`` method::

    class PaypalApp(AppConfig):
        …

        def installed(self, event):
            pass  # Your code here

Views
-----

Your plugin may define custom views. If you put an ``urls`` submodule into your
plugin module, pretalx will automatically import it and include it into the root
URL configuration with the namespace ``plugins:<label>:``, where ``<label>`` is
your Django app label.

.. WARNING:: If you define custom URLs and views, you are on your own
   with checking that the calling user has logged in, has appropriate permissions,
   etc. We plan on providing native support for this in a later version.

.. _Django app: https://docs.djangoproject.com/en/1.7/ref/applications/
.. _signal dispatcher: https://docs.djangoproject.com/en/1.7/topics/signals/
.. _namespace packages: http://legacy.python.org/dev/peps/pep-0420/
.. _entry point: https://pythonhosted.org/setuptools/setuptools.html#dynamic-discovery-of-services-and-plugins
.. _cookiecutter: https://cookiecutter.readthedocs.io/en/latest/
