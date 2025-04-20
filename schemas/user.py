from pydantic import BaseModel, EmailStr, ConfigDict, model_validator
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    nickname: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int


class UserVerified(User):
    is_verified: str

class UserVerify(BaseModel):
    email: Optional[EmailStr]
    nickname: Optional[str]
    verification_code: str

    @model_validator(mode='after')
    def validate_subject(self):
        if not self.email and not self.nickname:
            raise ValueError("The verify response does not have the required data. All required data: Code and email or nickname")
        return self

    class Config:
        extra = "forbid"

class UserInfo(BaseModel):
    username: Optional[str]
    age: Optional[str]
    gender: Optional[str]
    about: Optional[str]
    cof: Optional[str]
    # Count of followers
    
    

