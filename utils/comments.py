from typing import Optional, Dict, Any
from models.comments import Comment
from models.users import Users
from datetime import datetime

def build_comment_tree(
    comment: Comment,
    current_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """Рекурсивно строит дерево комментариев с информацией о лайках"""
    return {
        "id": comment.id,
        "text": comment.text,
        "author": comment.author.nickname,
        "author_id": comment.author.id,
        "created_at": comment.created_at,
        "like_count": comment.like_count,
        "liked_by_user": current_user_id is not None 
                         and any(u.id == current_user_id for u in comment.liked_by),
        "replies": [
            build_comment_tree(reply, current_user_id) 
            for reply in sorted(
                comment.replies,
                key=lambda x: x.created_at,
                reverse=True
            )
        ]
    }