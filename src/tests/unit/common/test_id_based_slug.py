import pytest
from pretalx.common.mixins import IdBasedSlug


def test_slug_create():
    s = IdBasedSlug()
    s.id = 5
    s.name = 'super Name'
    assert s.slug().startswith('5-') is True

def test_slug_parse():
    assert IdBasedSlug.id_from_slug('498-super_Name') == 498
