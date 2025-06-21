import pytest

from pretalx.agenda.recording import BaseRecordingProvider


def test_provider_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        BaseRecordingProvider("event").get_recording("submission")
