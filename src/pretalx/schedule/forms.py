from i18nfield.forms import I18nModelForm

from pretalx.common.forms import ReadOnlyFlag
from pretalx.schedule.models import Room


class RoomForm(ReadOnlyFlag, I18nModelForm):

    class Meta:
        model = Room
        fields = ['name', 'description', 'capacity', 'position']
