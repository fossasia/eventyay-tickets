import pytest

from pretalx.common.exporter import BaseExporter


def test_common_base_exporter_raises_proper_exceptions():
    exporter = BaseExporter(None)
    with pytest.raises(NotImplementedError):
        exporter.identifier
    with pytest.raises(NotImplementedError):
        exporter.verbose_name
    with pytest.raises(NotImplementedError):
        exporter.public
    with pytest.raises(NotImplementedError):
        exporter.icon
    with pytest.raises(NotImplementedError):
        exporter.render()
    with pytest.raises(NotImplementedError):
        str(exporter)
