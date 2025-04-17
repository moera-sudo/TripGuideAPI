from pydantic import BaseModel, EmailStr, model_validator, validator,  ValidationError
from typing import Optional

class TokenData(BaseModel):
    sub: str  # Или int, если используешь int ID
    nickname: Optional[str]
    email: Optional[EmailStr]
    exp: Optional[int] = None
    iat: Optional[int] = None
    token_type: Optional[str] = None

    @model_validator(mode='after')
    def validate_subject(self):
        if not self.sub or (not self.email and not self.nickname):
            raise ValueError("The token does not have the required data. All required data: id and email or nickname")
        return self

    class Config:
        extra = "forbid"

class Token(BaseModel):
    token: str
    token_type: str

    @validator('token_type')
    def validate_token_type(cls, v):
        if v not in ['refresh', 'access']:
            raise ValueError(f"Invalid token type. Acceptable only refresh/access. Got: {v}")
        return v
    
    class Config:
        extra = 'forbid'

class Tokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LoginRequest(BaseModel):
    email: Optional[str]
    nickname: Optional[str]
    password: str

    @model_validator(mode='after')
    def validate_login(self):
        if not self.email and not self.nickname:
            raise ValueError("Required data is missing")
        return self
