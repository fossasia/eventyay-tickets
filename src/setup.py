import os
from codecs import open
from distutils.command.build import build
from os import path

from setuptools import find_packages, setup

from pretalx import __version__ as pretalx_version

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
try:
    with open(path.join(here, '../README.rst'), encoding='utf-8') as f:
        long_description = f.read()
except:  # noqa
    long_description = ''


class CustomBuild(build):
    def run(self):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pretalx.settings")
        try:
            import django
        except (ImportError, ModuleNotFoundError):
            return
        django.setup()
        from django.conf import settings
        from django.core import management

        settings.COMPRESS_ENABLED = True
        settings.COMPRESS_OFFLINE = True

        management.call_command('compilemessages', verbosity=1)
        management.call_command('collectstatic', verbosity=1, interactive=False)
        management.call_command('compress', verbosity=1)
        build.run(self)


cmdclass = {
    'build': CustomBuild
}


setup(
    name='pretalx',
    version=pretalx_version,
    description='Conference organization: CfPs, scheduling, much more',
    long_description=long_description,
    url='https://pretalx.org',
    author='Tobias Kunze',
    author_email='rixx@cutebit.de',
    license='Apache License 2.0',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Other Audience',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Environment :: Web Environment',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.6',
        'Framework :: Django :: 2.0'
    ],

    keywords='conference cfp event barcamp',
    install_requires=[
        'bleach>=2.1.2,==2.1.*',
        'celery==4.1.*',
        'csscompressor==0.9.*',
        'cssutils==1.0.*',
        'Django==2.0.*',
        'django-bakery==0.12.*',
        'django-bootstrap4==0.0.4',
        'django-compressor==2.2.*',
        'django-csp==3.3.*',
        'django-filter==1.1.*',
        'django-formset-js-improved==0.5.0.1',
        'django-formtools==2.1.*',
        'django-hierarkey==1.0.*',
        'django-i18nfield==1.3.*',
        'django-libsass==0.7',
        'djangorestframework==3.7.*',
        'inlinestyler==0.2.*',
        'libsass<=0.13.1',  # May be removed once https://github.com/dahlia/libsass-python/pull/227 is merged
        'Markdown==2.6.*',
        'pytz',
        'reportlab==3.4.*',
        'requests',
        'rules==1.3.*',
        'urlman==1.2.*',
        'vobject==0.9.*',
        'whitenoise==3.3.*',
        'zxcvbn-python==4.4.*',
    ],
    extras_require={
        'dev': [
            'beautifulsoup4',
            'isort',
            'lxml',
            'pylama',
            'pytest',
            'pytest-cov',
            'pytest-django',
            'pytest-mock',
        ],
        'mysql': ['mysqlclient'],
        'postgres': ['psycopg2-binary'],
    },

    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    cmdclass=cmdclass,
)
