from pretix.base.forms import I18nModelForm
from pretix.base.models.organizer import OrganizerFooterLinkModel


class OrganizerFooterLinkForm(I18nModelForm):
    class Meta:
        model = OrganizerFooterLinkModel
        fields = ('label', 'url')
