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
    permission_to_recovery = Column(Boolean, default=False)
    verification_code = Column(String)
    username = Column(String)
    age = Column(Integer)
    gender = Column(String)
    about = Column(String)
    cof = Column(Integer)     
    # Count of followers
    avatar_url = Column(String, nullable=False, default='default.jpg')


    # TODO Добавить сюда relationship 
    refresh_tokens = relationship("RefreshTokens", back_populates="user", cascade="all, delete-orphan")
    guides = relationship("Guides", back_populates="author", cascade="all, delete-orphan", lazy="selectin")
    guide_likes = relationship("Guides", secondary="guide_likes", back_populates="liked_by", lazy="selectin")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    comment_likes = relationship(
        "Comment",
        secondary="comments_likes",
        back_populates="liked_by",
        lazy="selectin")


