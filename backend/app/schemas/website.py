from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool = True


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    permissions: dict = Field(default_factory=dict)


class AgentOut(BaseModel):
    id: int
    organization_id: int
    name: str
    description: str | None = None
    api_key_hash: str = "hidden"
    is_active: bool
    permissions: dict
    created_at: datetime
