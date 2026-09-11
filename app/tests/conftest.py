from pathlib import Path

from django.db import connections
from django.db.models.signals import pre_migrate
from django.dispatch import receiver


KNOWN_FAILURES_FILE = Path(__file__).with_name('known_failures.txt')


@receiver(pre_migrate, dispatch_uid='tests_enable_pg_trgm')
def enable_pg_trgm(sender, using, **kwargs):
    """Create the pg_trgm extension before the test database tables are built.

    Order models declare trigram GIN indexes. Migration ``base.0036`` creates the
    extension, but test runs without migrations build tables straight from the
    models, so the extension has to exist first. ``pre_migrate`` runs on each
    worker's own test database, so parallel workers cannot race on it.
    """
    if sender.label != 'base':
        return
    connection = connections[using]
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')


def pytest_addoption(parser):
    parser.addoption(
        '--skip-known-failures',
        action='store_true',
        help=f'Deselect the tests listed in tests/{KNOWN_FAILURES_FILE.name}.',
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption('skip_known_failures'):
        return
    known_failures = {
        line.strip()
        for line in KNOWN_FAILURES_FILE.read_text().splitlines()
        if line.strip() and not line.startswith('#')
    }
    deselected = [item for item in items if item.nodeid in known_failures]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = [item for item in items if item.nodeid not in known_failures]
