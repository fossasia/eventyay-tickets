from typing import Annotated

from pydantic import BaseModel, StringConstraints


class OAuth2Params(BaseModel):
    response_type: Annotated[str, StringConstraints(strip_whitespace=True)] = 'code'
    client_id: Annotated[str, StringConstraints(strip_whitespace=True)]
    redirect_uri: Annotated[str, StringConstraints(strip_whitespace=True)]
    scope: Annotated[str, StringConstraints(strip_whitespace=True)] = 'profile'
    state: Annotated[str, StringConstraints(strip_whitespace=True)]
