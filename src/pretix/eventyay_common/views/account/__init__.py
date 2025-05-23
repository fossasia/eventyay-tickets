from .basic import GeneralSettingsView, NotificationSettingsView, NotificationFlipOffView, HistoryView, DummyView
from .two_factor_auth import (
    TwoFactorAuthSettingsView,
    TwoFactorAuthEnableView,
    TwoFactorAuthDisableView,
    TwoFactorAuthDeviceAddView,
    TwoFactorAuthDeviceConfirmTOTPView,
    TwoFactorAuthDeviceConfirmWebAuthnView,
    TwoFactorAuthDeviceDeleteView,
    TwoFactorAuthRegenerateEmergencyView,
)
from .oauth import (
    OAuthAuthorizedAppListView,
    OAuthOwnAppListView,
    OAuthApplicationRegistrationView,
    OAuthApplicationUpdateView,
    OAuthApplicationRollView,
    OAuthApplicationDeleteView,
)
