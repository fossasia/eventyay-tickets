from .basic import GeneralSettingsView, NotificationSettingsView, DummyView
from .basic import (TwoFactorAuthSettingsView, TwoFactorAuthEnableView,
                      TwoFactorAuthDisableView, TwoFactorAuthDeviceAddView,
                      TwoFactorAuthDeviceConfirmTOTPView,
                      TwoFactorAuthDeviceConfirmWebAuthnView,
                      TwoFactorAuthDeviceDeleteView,
                      TwoFactorAuthRegenerateEmergencyView)
from .oauth import (OAuthAuthorizedAppListView, OAuthOwnAppListView, OAuthApplicationRegistrationView)
