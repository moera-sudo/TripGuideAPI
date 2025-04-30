from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class CommentBase(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    guide_id: int

class CommentCreate(CommentBase):
    parent_id: Optional[int] = None

class CommentResponse(CommentBase):
    id: int
    author_id: int
    created_at: datetime
    replies: List['CommentResponse'] = []
    
    class Config:
        orm_mode = True

# Для рекурсивной схемы
CommentResponse.update_forward_refs()