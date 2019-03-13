.. _maintenance:

Maintenance
===========

Once you have installed pretalx, you'll have to think about maintaining your
installation. These documents won't go into the (very important) tasks of
system maintenance, but they assume that you are keeping your servers up to
date on security updates, that your ports are closed as long as they do not
need to be publicly available, and that you generally follow best practices in
systems maintenance.

Updates
-------

.. warning:: While we try hard not to issue breaking updates, **please perform a backup before every upgrade**.

This guide assumes that you followed the :ref:`installation` documentation.

To upgrade pretalx, please first read through our :ref:`changelog` and if
available our release `blog post`_ to check for relevant update notes. Also,
make sure you have a current backup.

Next, please execute the following commands in the same environment (probably
your pretalx user, but maybe a virtualenv, if you chose a different
installation path) as your installation.

These first update the pretalx source, then update the database if necessary,
then rebuild changed static files, and then restart the pretalx service(s).
Please note that you will run into an entertaining amount of errors if you
forget to restart the service(s)::

    $ pip3 install --user -U pretalx
    $ python -m pretalx migrate
    $ python -m pretalx rebuild
    $ python -m pretalx regenerate_css
    # systemctl restart pretalx-web
    # systemctl restart pretalx-worker  # If you're running celery

Installing a fixed release
~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to upgrade pretalx to a specific release, you can substitute
``pretalx`` with ``pretalx==1.2.3`` in the ``pip install`` line above like
this::

    $ pip3 install --user pretalx==1.2.3

Installing a commit or a branch version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you're sure that you know what you're doing, you can also install a specific
commit or branch of pretalx (replace ``master`` with a short or long commit ID
for a specific commit)::

    $ pip3 install --user -U "git+git://github.com/pretalx/pretalx.git@master#egg=pretalx&subdirectory=src"


Backups
-------

There are essentially two things which you should create backups of:

Database
    Your SQL database (SQLite, MySQL or PostgreSQL). This is critical and you should **absolutely
    always create automatic backups of your database**. There are tons of tutorials on the
    internet on how to do this, and the exact process depends on the choice of your database.
    For MySQL, see ``mysqldump`` and for PostgreSQL, see the ``pg_dump`` tool. You probably
    want to create a cronjob or timer that does the backups for you on a regular schedule, and
    another one to rotate your backups regularly.

Data directory
    The data directory of your pretalkx configuration willl probably contain files that you should
    back up. If you did not specify a secret in your config file, back up the ``.secret`` text
    file in the data directory. If you lose your secret, all currently active user sessions,
    password reset links and similar things will be rendered invalid. Also, you should backup
    backup the ``media`` subdirectory of the data directory which contains all user-uploaded
    and generated files. This includes files you could in theory regenerate (talk and speaker images
    for social media, html exports), but also files that you or your users
    would need to re-upload (event logos, talk pictures, etc.). It is up to you if you
    create regular backups of this data, but we strongly advise you to do so. You can create
    backups e.g. using ``rsync``. There is a lot of information on the internet on how to create
    backups of folders on a server.

There is no need to create backups of the redis database, if you use it. We only use it for
non-critical, temporary or cached data.

.. _blog post: https://pretalx.com/p/news/
