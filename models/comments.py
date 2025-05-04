from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .basemodel import BaseModel

class Comment(BaseModel):
    __tablename__ = 'comments'
    
    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    like_count = Column(Integer, default=0)
    author_id = Column(Integer, ForeignKey('users.id'))
    guide_id = Column(Integer, ForeignKey('guides.id'))
    parent_id = Column(Integer, ForeignKey('comments.id'))
    
    # Relationships
    guide = relationship("Guides", back_populates="comments", lazy="selectin")
    author = relationship("Users", back_populates="comments", lazy="selectin")
    replies = relationship("Comment", 
                         back_populates="parent",
                         lazy="selectin",
                         cascade="all, delete",
                         order_by="Comment.created_at")
    parent = relationship("Comment", 
                        back_populates="replies",
                        remote_side=[id],
                        lazy="selectin")
    liked_by = relationship(
        "Users",
        secondary="comments_likes",
        back_populates="comment_likes",
        lazy="selectin"
    )
    
    def repr(self):
        return f"<Comment {self.id} by {self.author_id}>"