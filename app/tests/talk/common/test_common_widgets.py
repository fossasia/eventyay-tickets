from django.utils.datastructures import MultiValueDict

from eventyay.common.forms.widgets import SlidesWidget


def test_slides_widget_accepts_plain_dict_session_data():
    widget = SlidesWidget()

    value = widget.value_from_datadict(data={}, files=MultiValueDict(), name='slides')

    assert value == {
        'resources': [],
        'clear_ids': [],
    }
