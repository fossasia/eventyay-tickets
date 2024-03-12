.. _contributing:

Contributing to pretalx
=======================

.. highlight: console

You want to contribute? That’s great! Being an open source project, pretalx
thrives if it receives regular contributions from the community. Everyone is
able to contribute, and contributions can come in many forms: Code,
Documentation, :ref:`Translations<translating>`, Graphics, Feedback ….  We
appreciate them highly! If you’re not sure how to make something work, feel
free to `open a GitHub Discussion`_ about it.

Don’t forget to head over to :ref:`devsetup` to read about how to set up your
local copy of pretalx for development and testing.

Pull Request Workflow
---------------------

If you want to add some change to pretalx itself or its documentation, you can
do so by opening a Pull Request on GitHub_.

If you are not familiar with GitHub, the workflow is basically this: You
register an account on GitHub, then you “fork” pretalx, and work on your copy
of it until you’re done. Then, you submit your changes as a Pull Request. We’ll
review the PR and help you make any changes required to get it merged.  Have a
look at the `GitHub documentation`_ and other documentation on git for further
information.

We have tagged some issues as small_, and they are probably a good place to
start. If you want to tackle an issue, please leave a comment to make sure
nobody else will work on it in the meantime.

We recommend that you create a branch for every issue you work on. While our
continuous integration will run all tests and style checks against your PR, it
makes sense for you to run the test suite locally first, to work on any
problems ahead of time – but if you can’t figure out why tests are breaking,
don’t hesitate to submit your PR regardless. We’ll help you figure it out.

We also expect **tests** and **documentation** to be included with Pull
Requests if appropriate – if you’re not sure where to start on those, let us
know, and we’ll help.

Style Guide
-----------

Following a uniform style within a project makes it more maintainable. This
goes doubly for projects with many contributors, such as open source projects,
so we’d like to ask you to follow these style guide notes:

Code
~~~~

Generally, pretalx Python code follows `PEP8`_. We run ``flake8``, ``isort``
and ``black`` as style checkers, so those should help you if you’re not sure
how to format something. They are configured via the ``setup.cfg`` file in the
``src`` directory, and can be run like this::

    $ isort .
    $ black .
    $ flake8 .
    $ djhtml -i .

While we enforce no strict line length, please try to keep your lines **below
120 characters**. Other than that, we generally subscribe to the `Django
project style guide`_.

For JavaScript and (S)CSS files we follow the conventions established by
prettier_, with 2 spaces for indentation in (S)CSS files and 4 spaces in
JavaScript files::

    $ prettier --no-semi --write path/to/file

Changes should be covered by tests. Our tests run with pytest, so please use
their ``assert`` statement conventions.

Remember to mark all user-facing strings for **translation**, and please avoid
unnecessary changes to existing translations, as they require manual
re-translation in all languages.

Documentation
~~~~~~~~~~~~~

Documentation is written in Sphinx-style ReStructured Text format. Please wrap
lines at 80 characters.

If you are a native speaker: We’re always grateful for any improvements in
phrasing and clarity, particularly in our documentation.

Commit messages
~~~~~~~~~~~~~~~

Please wrap all lines of your commit messages at 72 characters at most – bonus
points if your first line is no longer than 50 characters. If your commit
message is longer than one line, the first line should be the subject, the
second line should be empty, and the remainder should be text.

If you want to address or close issues, please do so in the commit message
body. ``Closes #123`` or ``Refs #123`` will close the issue or show the
reference in the issue log on GitHub.

.. _open a GitHub discussion: https://github.com/pretalx/pretalx/discussions/new
.. _GitHub: https://github.com/pretalx/pretalx
.. _GitHub documentation: https://docs.github.com/en/pull-requests
.. _small: https://github.com/pretalx/pretalx/issues?q=is%3Aissue+is%3Aopen+label%3Asize%3Asmall
.. _PEP8: https://legacy.python.org/dev/peps/pep-0008/
.. _Django project style guide: https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/coding-style/
.. _prettier: https://prettier.io/
