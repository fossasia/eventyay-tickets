.. highlight:: python
   :linenothreshold: 5

.. _`plugin-auth`:

Writing an authentication plugin
================================

An authentication plugin allows you to add a new way to allow users to log in to your pretalx
instance. This can be useful if you want to integrate with an existing user database, or if
you want to use a different authentication method.

In this document, we will walk through the creation of an authentication plugin step by step.

If you’d like to look at a completed working authentication provider, take a look at
`pretalx-social-auth <https://github.com/adamskrz/pretalx-social-auth>`_, which also provides
a framework for adding custom OAuth2 providers.

Please read :ref:`Creating a plugin <pluginsetup>` first, if you haven’t already.

Authentication registration
---------------------------

The Pretalx auth plugin system is based around Django’s authentication backends, with a couple
of signals to integrate with the Pretalx interface.

First, follow Django’s documentation on writing an authentication backend, which must have the
methods ``get_user(user_id)`` and ``authenticate(request, **credentials)``.

To add your the backend to Pretalx, it needs to be added `authentication` section of the
`pretalx.cfg` file, in addition to the standard plugin registration e.g.:

.. code-block:: ini

   [authentication]
   additional_auth_backends=my_auth_plugin.auth.MyAuthBackend

   [project.entry-points."pretalx.plugin"]
   my_auth_plugin = "my_auth_plugin:PretalxPluginMeta"

The main signal used for authentication plugins (that require visiting a custom view) is the
`pretalx.common.signals.auth_html` signal. This adds additional HTML to the login page, for
example to add a login link to your custom authentication method. It also provides a `next_url`
parameter, which is the path the user should be redirected to after logging in.::

   from django.dispatch import receiver
   from django.utils.safestring import mark_safe

   from pretalx.common.signals import auth_html

   @receiver(auth_html)
   def render_login_auth_options(sender, request, next_url=None, **kwargs):
      login_url = reverse("plugins:my_auth_plugin:do_login")
      if next_url:
          login_url = f"{login_url}?next={next_url}"

      button = mark_safe(f"<a class="btn btn-lg btn-info btn-block" href="{login_url}">Sign in with Plugin</a>)
      return button

The `do_login` view should be implemented in your plugin, and should handle the actual
authentication process.

Most authentication plugins will store data against a user in the Pretalx database (e.g.
third-party ID), so you will need to create a model to store this data. To ensure this is
removed when the user is deleted, your plugin should listen for the `delete_user` signal and
remove any associated data for the `user` parameter.::

   from django.dispatch import receiver

   from pretalx.common.signals import delete_user

   @receiver(delete_user)
   def delete_user_data(sender, user, **kwargs):
      MyModel.objects.filter(user=user).delete()
