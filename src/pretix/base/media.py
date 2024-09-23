from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _


class BaseMediaType:
    medium_created_by_server = False
    supports_orderposition = False
    supports_giftcard = False

    @property
    def identifier(self):
        raise NotImplementedError("Identifier must be defined in subclasses.")

    @property
    def verbose_name(self):
        raise NotImplementedError("Verbose name must be defined in subclasses.")

    def generate_identifier(self, organizer):
        if self.medium_created_by_server:
            raise NotImplementedError("Identifier generation not implemented for this media type.")
        else:
            raise ValueError("This media type does not support identifier generation.")

    def is_active(self, organizer):
        return organizer.settings.get(f'reusable_media_type_{self.identifier}', as_type=bool, default=False)

    def handle_unknown(self, organizer, identifier, user, auth):
        """Override in subclass to handle unknown identifiers."""
        pass

    def handle_new(self, organizer, medium, user, auth):
        """Override in subclass to handle new mediums."""
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
            allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # Avoids similar characters like o,0,1,i for clarity
        )


class NfcUidMediaType(BaseMediaType):
    identifier = 'nfc_uid'
    verbose_name = _('NFC UID-based')
    medium_created_by_server = False
    supports_giftcard = True
    supports_orderposition = False

    def handle_unknown(self, organizer, identifier, user, auth):
        from pretix.base.models import GiftCard, ReusableMedium

        auto_create = organizer.settings.get(f'reusable_media_type_{self.identifier}_autocreate_giftcard', as_type=bool)
        if auto_create and not identifier.startswith("08"):
            with transaction.atomic():
                gc = GiftCard.objects.create(
                    issuer=organizer,
                    expires=organizer.default_gift_card_expiry,
                    currency=organizer.settings.get(f'reusable_media_type_{self.identifier}_autocreate_giftcard_currency'),
                )
                medium = ReusableMedium.objects.create(
                    type=self.identifier,
                    identifier=identifier,
                    organizer=organizer,
                    active=True,
                    linked_giftcard=gc
                )
                medium.log_action('pretix.reusable_medium.created.auto', user=user, auth=auth)
                gc.log_action('pretix.giftcards.created', user=user, auth=auth)
                return medium


class NfcMf0aesMediaType(BaseMediaType):
    identifier = 'nfc_mf0aes'
    verbose_name = 'NFC Mifare Ultralight AES'
    medium_created_by_server = False
    supports_giftcard = True
    supports_orderposition = False

    def handle_new(self, organizer, medium, user, auth):
        from pretix.base.models import GiftCard

        auto_create = organizer.settings.get(f'reusable_media_type_{self.identifier}_autocreate_giftcard', as_type=bool)
        if auto_create:
            with transaction.atomic():
                gc = GiftCard.objects.create(
                    issuer=organizer,
                    expires=organizer.default_gift_card_expiry,
                    currency=organizer.settings.get(f'reusable_media_type_{self.identifier}_autocreate_giftcard_currency'),
                )
                medium.linked_giftcard = gc
                medium.save()
                medium.log_action('pretix.reusable_medium.linked_giftcard.changed', user=user, auth=auth, data={'linked_giftcard': gc.pk})
                gc.log_action('pretix.giftcards.created', user=user, auth=auth)
                return medium


MEDIA_TYPES = {m.identifier: m for m in [BarcodePlainMediaType(), NfcUidMediaType(), NfcMf0aesMediaType()]}
