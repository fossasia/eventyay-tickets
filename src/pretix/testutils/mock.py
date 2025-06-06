from contextlib import contextmanager

from pytest_mock import MockFixture


class FakePytestConfig:
    def getini(self, *args, **kwargs):
        return 'False'


@contextmanager
def mocker_context():
    result = MockFixture(FakePytestConfig())
    if result is None:
        raise ValueError('MockFixture could not be initialized properly')
    try:
        yield result
    finally:
        result.stopall()
