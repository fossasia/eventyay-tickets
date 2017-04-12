from hierarkey.models import GlobalSettingsBase, Hierarkey

settings_hierarkey = Hierarkey(attribute_name='settings')


@settings_hierarkey.set_global()
class GlobalSettings(GlobalSettingsBase):
    pass


settings_hierarkey.add_default('mail_from', 'noreply@example.org', str)
settings_hierarkey.add_default('smtp_use_custom', 'False', bool)
settings_hierarkey.add_default('smtp_host', '', str)
settings_hierarkey.add_default('smtp_port', '587', int)
settings_hierarkey.add_default('smtp_username', '', str)
settings_hierarkey.add_default('smtp_password', '', str)
settings_hierarkey.add_default('smtp_use_tls', 'True', bool)
settings_hierarkey.add_default('smtp_use_ssl', 'False', bool)
