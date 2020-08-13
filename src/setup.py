import codecs
import sys
from distutils.command.build import build
from os import environ, path

from setuptools import find_packages, setup

from pretalx import __version__ as pretalx_version

here = path.abspath(path.dirname(__file__))

CURRENT_PYTHON = sys.version_info[:2]
REQUIRED_PYTHON = (3, 6)
if CURRENT_PYTHON < REQUIRED_PYTHON:
    sys.stderr.write(
        """
==========================
Unsupported Python version
==========================
This version of pretalx requires Python {}.{}, but you're trying to
install it on Python {}.{}.
This may be because you are using a version of pip that doesn't
understand the python_requires classifier. Make sure you
have pip >= 9.0 and setuptools >= 24.2, then try again:
    $ python -m pip install --upgrade pip setuptools
    $ python -m pip install pretalx
This will install the latest version of pretalx which works on your
version of Python.
""".format(
            *(REQUIRED_PYTHON + CURRENT_PYTHON)
        )
    )
    sys.exit(1)

# Get the long description from the relevant file
try:
    with codecs.open(path.join(here, "../README.rst"), encoding="utf-8") as f:
        long_description = f.read()
except:  # noqa
    long_description = ""


class CustomBuild(build):
    def run(self):
        environ.setdefault("DJANGO_SETTINGS_MODULE", "pretalx.settings")
        try:
            import django
        except ModuleNotFoundError:
            return
        django.setup()
        from django.conf import settings
        from django.core import management

        settings.COMPRESS_ENABLED = True
        settings.COMPRESS_OFFLINE = True

        management.call_command("compilemessages", verbosity=1)
        management.call_command("collectstatic", verbosity=1, interactive=False)
        management.call_command("compress", verbosity=1)
        build.run(self)


setup(
    name="pretalx",
    version=pretalx_version,
    license="Apache License 2.0",
    description="Conference organisation: CfPs, scheduling, much more",
    long_description=long_description,
    author="Tobias Kunze",
    author_email="r@rixx.de",
    url="https://pretalx.com",
    project_urls={
        "Documentation": "https://docs.pretalx.org",
        "Source": "https://github.com/pretalx/pretalx",
        "Issues": "https://github.com/pretalx/pretalx/issues",
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 3.0",
        "Intended Audience :: Developers",
        "Intended Audience :: Other Audience",
        "License :: OSI Approved",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    keywords="conference cfp event schedule",
    python_requires=">={}.{}".format(*REQUIRED_PYTHON),
    install_requires=[
        "beautifulsoup4~=4.9.0",  # https://bazaar.launchpad.net/~leonardr/beautifulsoup/bs4/view/head:/CHANGELOG
        "bleach~=3.1.0",  # https://bleach.readthedocs.io/en/latest/changes.html
        "celery~=4.4.0",  # search for "what's new" on http://docs.celeryproject.org/en/latest/
        "csscompressor~=0.9.0",  # 2017-11, no changelog, https://github.com/sprymix/csscompressor
        "cssutils~=1.0.0",  # https://pythonhosted.org/cssutils/CHANGELOG.html
        "defusedcsv~=1.1.0",  # https://github.com/raphaelm/defusedcsv
        "Django~=3.0.0",  # https://docs.djangoproject.com/en/2.0/releases/
        "django-bootstrap4~=2.0.0",  # http://django-bootstrap4.readthedocs.io/en/latest/history.html
        "django-compressor~=2.4.0",  # https://django-compressor.readthedocs.io/en/latest/changelog/
        "django-context-decorator",
        "django-countries~=6.1.0",  # https://github.com/SmileyChris/django-countries/blob/master/CHANGES.rst
        "django-csp~=3.7.0",  # https://github.com/mozilla/django-csp/blob/master/CHANGES
        "django-filter~=2.3.0",  # https://github.com/carltongibson/django-filter/blob/master/CHANGES.rst
        "django-formset-js-improved==0.5.0.2",  # no changelog, https://github.com/pretix/django-formset-js
        "django-formtools~=2.2.0",  # http://django-formtools.readthedocs.io/en/latest/changelog.html
        "django-hierarkey~=1.0.0",  # no changelog, https://github.com/raphaelm/django-hierarkey
        "django-i18nfield~=1.8.0",  # 2020-06, no changelog, https://github.com/raphaelm/django-i18nfield/
        "django-libsass~=0.8",  # inactive, https://github.com/torchbox/django-libsass/blob/master/CHANGELOG.txt
        "django-scopes~=1.2.0",  # https://github.com/raphaelm/django-scopes/releases
        "djangorestframework~=3.11.0",  # http://www.django-rest-framework.org/community/release-notes/
        "inlinestyler~=0.2.0",  # https://github.com/dlanger/inlinestyler/blob/master/CHANGELOG
        "libsass~=0.20.0",  # https://sass.github.io/libsass-python/changes.html
        "Markdown~=3.2.0",  # https://python-markdown.github.io/change_log/
        "publicsuffixlist~=0.7.0",
        "python-dateutil~=2.8.0",  # https://dateutil.readthedocs.io/en/stable/changelog.html
        "pytz",
        "qrcode~=6.1",  # https://github.com/lincolnloop/python-qrcode/blob/master/CHANGES.rst
        "reportlab~=3.5.0",  # https://www.reportlab.com/documentation/relnotes/
        "requests~=2.24.0",  # https://2.python-requests.org/en/master/community/updates/#release-and-version-history
        "rules~=2.2.0",  # https://github.com/dfunckt/django-rules/blob/master/CHANGELOG.md
        "urlman~=1.3.0",  # https://github.com/andrewgodwin/urlman/blob/master/CHANGELOG
        "vobject~=0.9.0",  # 2017-06, http://eventable.github.io/vobject/ look for "release"
        "whitenoise~=5.2.0",  # http://whitenoise.evans.io/en/stable/changelog.html
        "zxcvbn~=4.4.0",  # Nothing? https://github.com/dwolfhub/zxcvbn-python/issues/38
    ],
    extras_require={
        "dev": [
            "black",
            "check-manifest",
            "coverage",
            "docformatter",
            "Faker",
            "flake8",
            "freezegun",
            "isort",
            "lxml",
            "pytest",
            "pytest-cov",
            "pytest-django",
            "pytest-mock",
            "pytest-rerunfailures",
            "pytest-tldr",
            "pytest-xdist",
            "pywatchman",
            "responses",
            "urllib3",
        ],
        "mysql": ["mysqlclient"],
        "postgres": ["psycopg2-binary"],
        "redis": ["django_redis~=4.12.0", "redis~=3.5.0",],
    },
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    zip_safe=False,
    cmdclass={"build": CustomBuild},
)
