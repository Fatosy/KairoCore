from typing import List, Optional
from pydantic import BaseModel

class LoginBody(BaseModel):
    username: str
    password: str
    tenant_id: Optional[str] = None
    roles: Optional[List[str]] = None

class RefreshBody(BaseModel):
    refresh_token: str

class LogoutBody(BaseModel):
    refresh_token: str