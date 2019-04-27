.. _maintenance:

Maintenance
===========

Once you have installed pretalx, you’ll start thinking about maintaining your
installation. The following guide assumes that you perform general system
maintenance and monitoring. So please: keep your servers up to date on security
updates. Keep all non-public ports closed. Follow best practices.

Updates
-------

.. warning:: While we try hard not to issue breaking updates, **please perform
             a backup before every upgrade**.

This guide assumes that you followed the :ref:`installation` documentation.

We try to make upgrades as painless as possible. To this end, we provide
:ref:`changelog` and our release `blog post`_. Please read them – they contain
important upgrade notes and warnings. Also, make sure you have a current
backup.

Next, execute the following commands in the same environment as your
installation. This may be your pretalx user, or a virtualenv, if you chose a
different installation path.

These commands update pretalx first, then the database, then the static files.
Once you have executed these steps without seeing any errors, do not forget to
restart your service(s)::

    $ pip3 install --user -U pretalx
    $ python -m pretalx migrate
    $ python -m pretalx rebuild
    $ python -m pretalx regenerate_css
    # systemctl restart pretalx-web
    # systemctl restart pretalx-worker  # If you're running celery

Installing a fixed release
~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to upgrade pretalx to a specific release, you can pin the version
in the pip command. Substitute ``pretalx`` with ``pretalx==1.2.3`` in the pip
install line above like this::

    $ pip3 install --user pretalx==1.2.3

Installing a commit or a branch version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you're sure that you know what you're doing, you can also install a specific
commit or branch of pretalx. You can replace ``master`` with a short or long
commit ID for a specific commit::

    $ pip3 install --user -U "git+git://github.com/pretalx/pretalx.git@master#egg=pretalx&subdirectory=src"


Backups
-------

There are two things which you should create backups of:

Database

    Your SQL database (SQLite, MySQL or PostgreSQL). This is critical and you
    must **always always create automatic backups of your database**. There are
    tons of tutorials on the internet on how to do this, and the process
    depends on the choice of your database. For MySQL, see ``mysqldump`` and
    for PostgreSQL, see the ``pg_dump`` tool. You should create a cronjob or
    timer that does the backups for you on a regular schedule. Do not forget to
    add another one to rotate your backups.

Data directory
    The data directory of your pretalx configuration may contain files that you
    want to back up. If you did not specify a secret in your config file, back
    up the ``.secret`` text file in the data directory. If you lose the secret,
    all active user sessions, password reset links will be invalid. You should
    backup backup the ``media`` subdirectory of the data directory. It contains
    all user-uploaded and generated files. This includes files you could in
    theory regenerate (talk and speaker images for social media, html exports),
    but also files that you or your users would need to re-upload (event logos,
    talk pictures, etc.).

There is no need to create backups of the redis database, if you use it. We only use it for
non-critical, temporary or cached data.

.. _blog post: https://pretalx.com/p/news/
