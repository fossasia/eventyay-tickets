Release a pretalx version
=========================

So, you are a pretalx maintainer and want to release a new version? Woo-hoo, here we go!


System checks
-------------

1. Are you definitely in the branch and commit you think you are in?
2. Are all tests passing?
3. Have you deployed the release-ready commit to an instance? Did the upgrade work?
4. Check the translations: Are relevant strings still waiting for a translation?
5. Have you written (and not pushed) a blog post? It should contain at least major features and all contributors involved in the release.
6. Have you communicated your intentions and release timeline to the team?
7. Do the dependencies in ``requirements.txt`` and ``setup.py`` match?
8. Is the ``CHANGELOG.rst`` well-phrased and complete?

Takeoff and landing
-------------------

1. Bump version in ``src/pretalx/__init__.py`` and ``src/setup.py``.
2. Fill in the version and the release date in ``CHANGELOG.rst``.
3. Make a commit with the message ``Release vx.y.z``
4. Tag the commit: ``git tag -u F0DAD3990F9C816CFD30F8F329C085265D94C052 vx.y.z -m 'Release vx.y.z'``
5. Remove old build artifacts: ``rm -rf dist/ build/ pretalx.egg-info``
6. Build a new release: ``python setup.py sdist``
7. Sign the release: ``gpg --default-key F0DAD3990F9C816CFD30F8F329C085265D94C052 --detach-sign -a dist/pretalx-x.y.z.tar.gz``
8. Upload the release: ``twine upload dist/pretalx-x.y.z.tar.gz dist/pretalx-x.y.z.tar.gz.asc``
9. Push the release: ``git push && git push --tags``
10. Add the release on GitHub (upload the tar.gz you uploaded to PyPI, and add the CHANGELOG section): https://github.com/pretalx/pretalx/releases
11. Push the blog post.
