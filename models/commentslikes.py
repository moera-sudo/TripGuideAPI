from sqlalchemy import Column, ForeignKey

from .basemodel import BaseModel

class CommentsLikes(BaseModel):
    __tablename__ = "comments_likes"

    user_id = Column(ForeignKey("users.id"), primary_key=True)
    comment_id = Column(ForeignKey("comments.id"), primary_key=True)

