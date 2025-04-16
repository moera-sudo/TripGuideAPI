from pydantic import BaseModel, EmailStr, model_validator, validator,  ValidationError
from typing import Optional, Dict, Any, List
from enum import Enum

class EmailType(str, Enum):
    VERIFICATION = "verification"
    PASSWORD_RECOVERY = "password_recovery"
    WELCOME = "welcome"
    NOTIFICATION = "notification"


class EmailSchema(BaseModel):
    """Schema для данных электронной почты"""
    email: List[EmailStr]
    subject: str
    body: Dict[str, Any]
