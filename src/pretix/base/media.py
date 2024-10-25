from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _


class BaseMediaType:
    medium_created_by_server = False
    supports_orderposition = False
    supports_giftcard = False

    @property
    def identifier(self):
        raise NotImplementedError()

    @property
    def verbose_name(self):
        raise NotImplementedError()

    def generate_identifier(self, organizer):
        if self.medium_created_by_server:
            raise NotImplementedError()
        else:
            raise ValueError("Media type does not allow to generate identifier")

    def is_active(self, organizer):
        return organizer.settings.get(f'reusable_media_type_{self.identifier}', as_type=bool, default=False)

    def handle_unknown(self, organizer, identifier, user, auth):
        pass

    def handle_new(self, organizer, medium, user, auth):
        pass

    def __str__(self):
        return str(self.verbose_name)


class BarcodePlainMediaType(BaseMediaType):
    identifier = 'barcode'
    verbose_name = _('Barcode / QR-Code')
    medium_created_by_server = True
    supports_giftcard = False
    supports_orderposition = True

    def generate_identifier(self, organizer):
        return get_random_string(
            length=organizer.settings.reusable_media_type_barcode_identifier_length,
            # Exclude o,0,1,i to avoid confusion with bad fonts/printers
            # We use upper case to make collisions with ticket secrets less likely
            allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        )


class NfcUidMediaType(BaseMediaType):
    identifier = 'nfc_uid'
    verbose_name = _('NFC UID-based')
    medium_created_by_server = False
    supports_giftcard = True
    supports_orderposition = False

    def handle_unknown(self, organizer, identifier, user, auth):
        from pretix.base.models import GiftCard, ReusableMedium

        if organizer.settings.get(f'reusable_media_type_{self.identifier}_autocreate_giftcard', as_type=bool):
            if identifier.startswith("08"):
                # Don't create gift cards for NFC UIDs that start with 08, which represents NFC cards that issue random
                # UIDs on every read, so they won't be useful.
                return
            with transaction.atomic():
                gc = GiftCard.objects.create(
                    issuer=organizer,
                    expires=organizer.default_gift_card_expiry,
                    currency=organizer.settings.get(f'reusable_media_type_{self.identifier}_autocreate_giftcard_currency'),
                )
                m = ReusableMedium.objects.create(
                    type=self.identifier,
                    identifier=identifier,
                    organizer=organizer,
                    active=True,
                    linked_giftcard=gc
                )
                m.log_action(
                    'pretix.reusable_medium.created.auto',
                    user=user, auth=auth,
                )
                gc.log_action(
                    'pretix.giftcards.created',
                    user=user, auth=auth,
                )
                return m


class NfcMf0aesMediaType(BaseMediaType):
    identifier = 'nfc_mf0aes'
    verbose_name = 'NFC Mifare Ultralight AES'
    medium_created_by_server = False
    supports_giftcard = True
    supports_orderposition = False

    def handle_new(self, organizer, medium, user, auth):
        from pretix.base.models import GiftCard

        if organizer.settings.get(f'reusable_media_type_{self.identifier}_autocreate_giftcard', as_type=bool):
            with transaction.atomic():
                gc = GiftCard.objects.create(
                    issuer=organizer,
                    expires=organizer.default_gift_card_expiry,
                    currency=organizer.settings.get(f'reusable_media_type_{self.identifier}_autocreate_giftcard_currency'),
                )
                medium.linked_giftcard = gc
                medium.save()
                medium.log_action(
                    'pretix.reusable_medium.linked_giftcard.changed',
                    user=user, auth=auth,
                    data={
                        'linked_giftcard': gc.pk
                    }
                )
                gc.log_action(
                    'pretix.giftcards.created',
                    user=user, auth=auth,
                )
                return medium


MEDIA_TYPES = {
    m.identifier: m for m in [
        BarcodePlainMediaType(),
        NfcUidMediaType(),
        NfcMf0aesMediaType(),
    ]
}
