Release a pretalx version
=========================

You are a pretalx maintainer and want to release a new version? Hold on to your fancy hat or your favourite socks, here we go!

Boarding checks
---------------

1. Are the translations up to date?
2. Are there warnings about missing migrations?
3. Any blockers to see `here <https://github.com/pretalx/pretalx/issues?q=is%3Aissue+is%3Aopen+label%3Aissue%3Abug>`_?
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

Take-off and landing
--------------------

1. Bump version in ``src/pretalx/__init__.py``.
2. Add the release to the :ref:`changelog`.
3. Make a commit with the message ``Release vx.y.z``
4. Tag the commit: ``git tag -u F0DAD3990F9C816CFD30F8F329C085265D94C052 vx.y.z -m 'Release vx.y.z'``
5. Remove old build artefacts: ``rm -rf dist/ build/ pretalx.egg-info``
6. Build a new release: ``python setup.py sdist``
7. Sign the release: ``gpg --default-key F0DAD3990F9C816CFD30F8F329C085265D94C052 --detach-sign -a dist/pretalx-x.y.z.tar.gz``
8. Upload the release: ``twine upload dist/pretalx-x.y.z.tar.gz dist/pretalx-x.y.z.tar.gz.asc``
9. Push the release: ``git push && git push --tags``
10. Install/update the package somewhere.
11. Add the release on `GitHub <https://github.com/pretalx/pretalx/releases>`_ (upload the archive you uploaded to PyPI, and add a link to the correct section of the :ref:`changelog`)
12. Push the blog post.
13. Upgrade `the docker repository <https://github.com/pretalx/pretalx-docker>`_
14. Switch to master branch
15. Copy release note to changelog and increment version number.
16. Update version numbers in update checker and deploy.
