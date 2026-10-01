from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=10, max_length=128)
    organisation_name: str = Field(min_length=2, max_length=160)
    organisation_slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class OrganisationResponse(BaseModel):
    id: int
    name: str
    slug: str
    role: str
