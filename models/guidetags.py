from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .basemodel import BaseModel


class GuideTags(BaseModel):
    __tablename__ = "guide_tags"

    guide_id = Column(ForeignKey("guides.id"), primary_key=True)
    tag_id = Column(ForeignKey("tags.id"), primary_key=True)
