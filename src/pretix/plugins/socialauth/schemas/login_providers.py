from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    state: bool = Field(description='State of this providers', default=False)
    client_id: str = Field(description='Client ID of this provider', default='')
    secret: str = Field(description='Secret of this provider', default='')


class LoginProviders(BaseModel):
    mediawiki: ProviderConfig = Field(default_factory=ProviderConfig)
    github: ProviderConfig = Field(default_factory=ProviderConfig)
    google: ProviderConfig = Field(default_factory=ProviderConfig)

    class Config:
        extra = 'forbid'
