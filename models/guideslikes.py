from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from .basemodel import BaseModel

class GuideLikes(BaseModel):
    __tablename__ = "guide_likes"

    user_id = Column(ForeignKey("users.id"), primary_key=True)
    guide_id = Column(ForeignKey("guides.id"), primary_key=True)