from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from .basemodel import BaseModel


class Tags(BaseModel):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    guides = relationship("Guides", secondary="guide_tags", back_populates="tags", lazy="selectin")
