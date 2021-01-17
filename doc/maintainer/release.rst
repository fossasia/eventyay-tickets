Release a pretalx version
=========================

You are a pretalx maintainer and want to release a new version? Hold on to your fancy hat or your favourite socks, here we go!

Boarding checks
---------------

1. Are the translations up to date?
2. Are there warnings about missing migrations?
3. Any blockers to see `here <https://github.com/pretalx/pretalx/issues?q=is%3Aopen+is%3Aissue+label%3A%22issue%3Abug+%F0%9F%90%9B%22>`_?
4. Are there any TODOs that you have to be resolve?
5. Are there any ``@pytest.mark.xfail`` that you have to resolve?
6. Are the :ref:`changelog` well-phrased and complete?
7. Are there `open pull requests <https://github.com/pretalx/pretalx/pulls>`_ that you should merge?
8. Is the `code coverage <https://codecov.io/gh/pretalx/pretalx/commits>`_ all right?

System checks
-------------

1. Are you in the branch and commit you think you are in?
2. Are all tests passing? (On Travis, or locally if you're willing to check all databases or are under time pressure.)
3. Have you deployed the release-ready commit to an instance? Did the upgrade work?
4. Have you written (and not pushed) a blog post? It should contain at least major features and all contributors involved in the release. ``git shortlog -ns vx.y.z..master``.
5. Have you communicated your intentions and release time line to the team?
6. Is your virtualenv active?
7. Run ``check-manifest`` **locally**.

Take-off and landing
--------------------

1. Bump version in ``src/pretalx/__init__.py``.
2. Update the supported version in ``SECURITY.md`` if the release is not just a patch release.
3. Update the translation percentages from `here <https://translate.pretalx.com/projects/pretalx/pretalx/#translations>`_.
4. Add the release to the :ref:`changelog`.
5. Make a commit with the message ``Release vx.y.z``
6. Tag the commit: ``git tag -u F0DAD3990F9C816CFD30F8F329C085265D94C052 vx.y.z -m 'Release vx.y.z'``
7. Remove old build artefacts: ``rm -rf dist/ build/ pretalx.egg-info``
8. Build a new release: ``python setup.py sdist``
9. Sign the release: ``gpg --default-key F0DAD3990F9C816CFD30F8F329C085265D94C052 --detach-sign -a dist/pretalx-x.y.z.tar.gz``
10. Upload the release: ``twine upload dist/pretalx-x.y.z.tar.gz dist/pretalx-x.y.z.tar.gz.asc``
11. Push the release: ``git push && git push --tags``
12. Install/update the package somewhere.
13. Add the release on `GitHub <https://github.com/pretalx/pretalx/releases>`_ (upload the archive you uploaded to PyPI, and add a link to the correct section of the :ref:`changelog`)
14. Push the blog post.
15. Upgrade `the docker repository <https://github.com/pretalx/pretalx-docker>`_ to the current commit **and tag the commit as vx.y.z**.
16. Switch to master branch
17. Copy release note to changelog and increment version number.
18. Update version numbers in update checker and deploy.
