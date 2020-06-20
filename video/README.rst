venueless
=========

.. image:: https://readthedocs.org/projects/venueless/badge/?version=latest
   :target: https://venueless.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. image:: https://github.com/venueless/venueless/workflows/Server%20tests/badge.svg
   :target: https://github.com/venueless/venueless/actions
   :alt: Server tests

.. image:: https://codecov.io/gh/venueless/venueless/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/venueless/venueless

venueless allows you to run events fully online. You can make use of different modules including live video streams, interactive video calls, group chats and more.

venueless is brought to you by `pretix`_, `pretalx`_, and `rash.codes`_.

**This project is in a development stage and requires in-depth technical knowledge for production use.**

License
-------

venueless is released under the terms of the Business Source License 1.1. See the ``LICENSE`` file for the full
license text as well as the license parameters.

License FAQ
^^^^^^^^^^^

venueless is not released under an open source license (according to the OSI definition), but an "eventually open
source" license. While the BSL becomes more common, this is still a rare choice, so we'd like to answer a few
questions you might have.

What does "eventually open source" mean?
""""""""""""""""""""""""""""""""""""""""

While the BSL is not an open source license, it contains a clause that makes sure that the code will automatically be
re-released under a fully free and open source license (Apache License 2.0 in our case) at a specified change date.
With every major update of venueless, we will update this change date to be 24 months in the future starting from
the date of that release.

If you use a version after its change date, you will no longer need to obey the terms of the BSL, but can use the
project as if it were licensed with the Apache License.

Can I use venueless for my event for free?
""""""""""""""""""""""""""""""""""""""""""

Yes, absolutely! You can set up venueless on a server under your control to host as many events as you like without
any limitations.

Can I fork and change venueless?
""""""""""""""""""""""""""""""""

Yes, you are allowed to copy and modify venueless, create derivative works, and redistribute them, as long as you
obey the license terms and all derived work carries the same restrictions until the change date.

Can I offer a hosted version of venueless to my clients?
""""""""""""""""""""""""""""""""""""""""""""""""""""""""

No, this is basically the only thing you can't do. You can only use venueless for events hosted by your organization,
but you can't provide it as a service to other organizations.

Can I integrate parts of venueless in my Open Source Project?
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Unfortunately not. If there's a component you'd like to re-use, please reach out to us and we'll check if we can
extract that component into a re-usable module that we release under a more permissive license.

Additionally, you can check if the component was already in venueless in a version on which the BSL has already
expired (see above).

Are there other licensing options?
""""""""""""""""""""""""""""""""""

Yes, if you want to use venueless in a way that is not allowed under its license, we are able to provide you with
additional licensing options. Please talk to us :)

Why did you choose the BSL?
"""""""""""""""""""""""""""

We love open source, and we wanted to release this project's source code early on to allow the community to play with
it and use it for community events for free.

At the same time, we're trying to build a business model based on the project in order to allow us to spend
significant time resources on its development.

Finding a balance between these two goals is hard, and there's no final solution to the OSS funding problem. In our
experience, support contracts alone are not sufficient to fund the development of a project with an audience like
this, and we wanted to fully release the whole project instead of going for an "open core" model in which we only
release part of it.

Therefore, we've decided to chose providing a Software as a Service offering of this software as our primary business
model, and the BSL allows us to protect ourselves against players with a bigger marketing budget and no interest in
contributing back to the project using our work to compete with us directly.
We'd like to refer to this `Sentry blogpost`_ for a more in-depth explanation of many reasons behind the choice.

Unlike a more traditional dual licensing approach, the BSL's change date mechanism adds a safeguard against us going
out of business or just losing interest in the project: If we abandon it, it will automatically fully belong to the
community.

.. _pretalx: https://pretalx.com
.. _pretix: https://pretix.eu
.. _Sentry blogpost: https://blog.sentry.io/2019/11/06/relicensing-sentry
.. _rash.codes: https://rash.codes/
