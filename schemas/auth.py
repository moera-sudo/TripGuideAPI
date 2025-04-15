from pydantic import BaseModel, EmailStr, model_validator, validator,  ValidationError
from typing import Optional

class TokenData(BaseModel):
    sub: int
    nickname: Optional[str]
    email: Optional[EmailStr]
    #TODO В будущем при добавлении админки надо будет добавить сюда is_admin и permissions

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


class LoginRequest(BaseModel):
    email: Optional[EmailStr]
    nickname: Optional[str]
    password: str

    @model_validator(mode='after')
    def validate_login(self):
        if not self.email and not self.nickname:
            raise ValueError("Required data is missing")
        return self
