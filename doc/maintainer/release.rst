Release a pretalx version
=========================

You are a pretalx maintainer and want to release a new version? Woo-hoo, here we go!

Boarding checks
---------------

1. Are the translations up to date?
2. Are there warnings about missing migrations?
3. Any blockers to see here? https://github.com/pretalx/pretalx/issues?q=is%3Aissue+is%3Aopen+label%3Aissue%3Abug
4. Is the ``CHANGELOG.rst`` well-phrased and complete?

System checks
-------------

1. Are you in the branch and commit you think you are in?
2. Are all tests passing? (On Travis, locally only if you're willing to check all databases or are under time pressure.)
3. Have you deployed the release-ready commit to an instance? Did the upgrade work?
4. Have you written (and not pushed) a blog post? It should contain at least major features and all contributors involved in the release, i.e. ``git shortlog -ns vx.y.z..master``.
5. Have you communicated your intentions and release timeline to the team?

Takeoff and landing
-------------------

1. Bump version in ``src/pretalx/__init__.py``.
2. Fill in the version and the release date in ``CHANGELOG.rst``.
3. Make a commit with the message ``Release vx.y.z``
4. Tag the commit: ``git tag -u F0DAD3990F9C816CFD30F8F329C085265D94C052 vx.y.z -m 'Release vx.y.z'``
5. Remove old build artifacts: ``rm -rf dist/ build/ pretalx.egg-info``
6. Build a new release: ``python setup.py sdist``
7. Sign the release: ``gpg --default-key F0DAD3990F9C816CFD30F8F329C085265D94C052 --detach-sign -a dist/pretalx-x.y.z.tar.gz``
8. Upload the release: ``twine upload dist/pretalx-x.y.z.tar.gz dist/pretalx-x.y.z.tar.gz.asc``
9. Push the release: ``git push && git push --tags``
10. Install/update the package somewhere.
11. Add the release on GitHub (upload the tar.gz you uploaded to PyPI, and add the CHANGELOG section): https://github.com/pretalx/pretalx/releases
12. Push the blog post.
