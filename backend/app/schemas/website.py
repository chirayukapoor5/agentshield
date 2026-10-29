from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


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
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    is_active: bool = True


class WebsiteCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    url: HttpUrl


class WebsiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    name: str
    url: str
    status: str
    owner_verified: bool
    verification_status: str
    verified_at: datetime | None = None
    created_at: datetime


class WebsiteCreated(WebsiteOut):
    verification_token: str
    verification_dns_name: str
    verification_instructions: str


class WebsiteVerificationOut(BaseModel):
    website_id: int
    verification_status: str
    verification_dns_name: str
    verification_token: str
    expires_at: datetime
    instructions: str
