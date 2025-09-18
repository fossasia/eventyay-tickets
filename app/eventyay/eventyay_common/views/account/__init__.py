from .basic import DummyView, GeneralSettingsView, HistoryView, NotificationFlipOffView, NotificationSettingsView
from .oauth import (
    OAuthApplicationDeleteView,
    OAuthApplicationRegistrationView,
    OAuthApplicationRollView,
    OAuthApplicationUpdateView,
    OAuthAuthorizedAppListView,
    OAuthAuthorizedAppRevokeView,
    OAuthOwnAppListView,
)
from .two_factor_auth import (
    TwoFactorAuthDeviceAddView,
    TwoFactorAuthDeviceConfirmTOTPView,
    TwoFactorAuthDeviceConfirmWebAuthnView,
    TwoFactorAuthDeviceDeleteView,
    TwoFactorAuthDisableView,
    TwoFactorAuthEnableView,
    TwoFactorAuthRegenerateEmergencyView,
    TwoFactorAuthSettingsView,
)
