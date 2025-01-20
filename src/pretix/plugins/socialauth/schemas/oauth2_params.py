from pydantic import BaseModel, Field


class OAuth2Params(BaseModel):
    response_type: str = Field(default="code")
    client_id: str
    redirect_uri: str
    scope: str = Field(default="profile")
    state: str
