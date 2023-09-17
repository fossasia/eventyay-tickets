Release a pretalx version
=========================

You are a pretalx maintainer and want to release a new version? Hold on to your fancy hat or your favourite socks, here we go!

Boarding checks
---------------

1. Are there pending migrations from `Weblate <https://translate.pretalx.com/projects/pretalx/pretalx/#repository>`_? Merge them.
2. Are the translation files up to date?
3. Are there pending checks for bad translations on Weblate?
4. If new translations were added, add new fullcalendar locales (you have to download the `release archive <https://github.com/fullcalendar/fullcalendar/releases/download/v6.1.5/fullcalendar-6.1.5.zip>`_) and extract the locales from there), and make sure that flags (in input fields) for the new locale are shown.
5. Are there warnings about missing migrations?
6. Any blockers to see `here <https://github.com/pretalx/pretalx/issues?q=is%3Aopen+is%3Aissue+label%3A%22type%3A+bug%22+>`_?
7. Are there any TODOs that you have to be resolve?
8. Are there any ``@pytest.mark.xfail`` that you have to resolve?
9. Are the :ref:`changelog` well-phrased and complete?
10. Are there `open pull requests <https://github.com/pretalx/pretalx/pulls>`_ that you should merge?

System checks
-------------

1. Are you in the branch and commit you think you are in?
2. Are all tests passing?
3. Have you deployed the release-ready commit to an instance? Did the upgrade work?
4. Have you written (and not pushed) a blog post? It should contain at least major features and all contributors involved in the release. ``git shortlog -ns vx.y.z..main``.
5. Have you told people who may need to know about the release ahead of time? (Plugin developers, clients, self-hosting instances, etc.)
6. Is your virtualenv active?

Take-off and landing
--------------------

1. Clone pretalx into a clean repo: ``git clone git@github.com:pretalx/pretalx pretalx-release && workon pretalx``
2. Run ``check-manifest`` **locally**.
3. Bump version in ``src/pretalx/__init__.py``.
4. Update the translation percentages from `here <https://translate.pretalx.com/projects/pretalx/pretalx/#translations>`_.
5. Add the release to the :ref:`changelog`.
6. Make a commit with the message ``Release vx.y.z``
7. Tag the commit: ``git tag vx.y.z -m``
8. Remove old build artefacts: ``rm -rf dist/ build/ pretalx.egg-info``
9. Build a new release: ``python -m build -n``
10. Upload the release: ``twine upload dist/pretalx-x.y.z.tar.gz``
11. Push the release: ``git push && git push --tags``
12. Install/update the package somewhere.
13. Add the release on `GitHub <https://github.com/pretalx/pretalx/releases>`_ (upload the archive you uploaded to PyPI, and add a link to the correct section of the :ref:`changelog`)
14. Push the blog post.
15. Upgrade `the docker repository <https://github.com/pretalx/pretalx-docker>`_ to the current commit **and tag the commit as vx.y.z**.
16. Increment version number to version+1.dev0 in ``src/pretalx/__init__.py``.
17. Update version numbers in update checker and deploy.
