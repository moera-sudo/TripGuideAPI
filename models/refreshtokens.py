from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import datetime

from .basemodel import BaseModel


class RefreshTokens(BaseModel):
    __tablename__ = 'refresh_tokens'

    id = Column(Integer, primary_key=True, index=True)

    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("Users", back_populates="refresh_tokens")

    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    @property
    def is_expired(self):
        """Проверка, истек ли срок действия токена"""
        return datetime.datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self):
        """Проверка, действителен ли токен"""
        return not self.is_revoked and not self.is_expired