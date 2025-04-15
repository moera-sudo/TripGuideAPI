from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from .basemodel import BaseModel

class Users(BaseModel):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String)
    username = Column(String)
    age = Column(Integer)
    gender = Column(String)
    about = Column(String)
    cof = Column(Integer) 
    # Count of followers

    # TODO Добавить сюда relationship 