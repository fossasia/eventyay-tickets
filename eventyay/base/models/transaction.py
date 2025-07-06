import contextlib

from django.db import transaction


@contextlib.contextmanager
def rolledback_transaction():
    """This context manager runs your code in a database transaction that will
    be rolled back in the end.

    This can come in handy to simulate the effects of a database
    operation that you do not actually want to perform. Note that
    rollbacks are a very slow operation on most database backends. Also,
    long-running transactions can slow down other operations currently
    running and you should not use this in a place that is called
    frequently.
    """

    class DummyRollbackError(Exception):
        pass

    try:
        with transaction.atomic():
            yield
            raise DummyRollbackError()
    except DummyRollbackError:
        pass
    else:  # pragma: no cover
        raise Exception("Invalid state, should have rolled back.")
