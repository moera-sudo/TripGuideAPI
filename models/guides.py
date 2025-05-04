from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from .basemodel import BaseModel


class Guides(BaseModel):
    __tablename__ = 'guides'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow())
    like_count = Column(Integer, default=0)

    content_file_url = Column(String, nullable=False, unique=True)
    head_image_url = Column(String, nullable=False)

    author_id = Column(Integer, ForeignKey('users.id'))
    author = relationship("Users", back_populates="guides", lazy="selectin")

    # guide_tags = relationship("GuideTag", back_populates="guide", cascade="all, delete-orphan")
    tags = relationship("Tags", secondary="guide_tags", back_populates="guides", lazy="selectin")
    liked_by = relationship("Users", secondary="guide_likes", back_populates="guide_likes", lazy="selectin")
    comments = relationship("Comment", back_populates="guide", lazy="selectin")