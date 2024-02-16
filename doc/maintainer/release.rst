Release a pretalx version
=========================

You are a pretalx maintainer and want to release a new version? Hold on to your fancy hat or your favourite socks, here we go!

Boarding checks
---------------

1. Are the translation files up to date?
2. Are there pending checks for bad translations on Weblate?
3. Are there pending translations from `Weblate <https://translate.pretalx.com/projects/pretalx/pretalx/#repository>`_? Merge them.
4. Are all locales with more than 75% coverage included in the release?
5. Update the translation percentages from `translate.pretalx.com <https://translate.pretalx.com/projects/pretalx/pretalx/#translations>`_.
6. If new translations were added, add new fullcalendar locales (you have to download the `release archive <https://github.com/fullcalendar/fullcalendar/releases/download/v6.1.5/fullcalendar-6.1.5.zip>`_) and extract the locales from there), and make sure that flags (in input fields) for the new locale are shown.
7. Are there warnings about missing migrations?
8. Any blockers to see `in our issues <https://github.com/pretalx/pretalx/issues?q=is%3Aopen+is%3Aissue+label%3A%22type%3A+bug%22+>`_?
9. Are there any TODOs that you have to resolve?
10. Are there any ``@pytest.mark.xfail`` that you have to resolve?
11. Are the :ref:`changelog` well-phrased and complete?
12. Are there `open pull requests <https://github.com/pretalx/pretalx/pulls>`_ that you should merge?
13. Are all tests passing in CI?
14. Have you written (and not pushed) a blog post? It should contain at least major features and all contributors involved in the release.

System checks
-------------

1. Deploy the release-ready commit to an instance. Check if the upgrade and the instance works.
2. Clone pretalx into a clean repo: ``git clone git@github.com:pretalx/pretalx pretalx-release && mkvirtualenv pretalx-release && pip install -e .[dev]``
3. Run ``pytest`` **locally**.
5. Run ``check-manifest`` **locally**.

Take-off and landing
--------------------

1. Bump version in ``src/pretalx/__init__.py``.
2. Add the release to the :ref:`changelog`.
3. Make a release commit: ``RELEASE=vx.y.z && git commit -am "Release $RELEASE" && git tag $RELEASE -m "Release $RELEASE"``
4. Build a new release: ``rm -rf dist/ build/ pretalx.egg-info && python -m build -n``
5. Upload the release: ``twine upload dist/pretalx-x.y.z.tar.gz``
6. Push the release: ``git push && git push --tags``
7. Install/update the package somewhere.
8. Add the release on `GitHub <https://github.com/pretalx/pretalx/releases>`_ (upload the archive you uploaded to PyPI, and add a link to the correct section of the :ref:`changelog`)
9. Publish the blog post.
10. Upgrade `the docker repository <https://github.com/pretalx/pretalx-docker>`_ to the current commit **and tag the commit as vx.y.z**.
11. Increment version number to version+1.dev0 in ``src/pretalx/__init__.py``.
12. Update version numbers in update checker and deploy.
13. ``rm -rf pretalx-release && deactivate && rmvirtualenv pretalx-release``
14. Update any plugins waiting for the new release.
15. Check if the docker image build was successful.
