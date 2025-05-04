import os
import re
import shutil
from typing import List
import httpx
import aiofiles
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import delete, exists, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import logger

from config.appsettings import Settings
from config.database import get_db
from config.config import content_dir
from models.users import Users
from models.guides import Guides
from models.tags import Tags
from schemas.guides import GuideBase
from schemas.comment import CommentCreate, CommentResponse
from models.guideslikes import GuideLikes
from models.guidetags import GuideTags
from models.comments import Comment
from models.commentslikes import CommentsLikes
from utils.current_user import get_current_user
from utils.recommendation_service import get_recommendation_service
from services.RecommendationService import RecommendationService
from services.GuideService import GuideService


router = APIRouter(
    prefix='/comments',
    tags=['comments']    
)

#TODO Нужно добавить роуты для создания, удаления и редактирование комментариев + лайк

@router.post("/add", status_code=status.HTTP_201_CREATED)
async def create_comment(
    data: CommentCreate, db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)
): 
    try:

        guide = await GuideService.get_guide_by_id(db, data.guide_id)

        if not guide:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guide not found")
        
        # Проверка parent_id если указан
        if data.parent_id:
            parent = await db.execute(
                select(Comment).where(Comment.id == data.parent_id)
            )
            if not parent.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Parent comment not found")
        
        db_comment = Comment(
            text=data.text,
            author_id=user.id,
            guide_id=data.guide_id,
            parent_id=data.parent_id
        )
        
        db.add(db_comment)
        await db.commit()
        await db.refresh(db_comment)

        return {"message": f"Comment for guide with id: {data.guide_id} added"}
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while creating comment: {e}"
        )

@router.post("/like/{comment_id}", status_code=status.HTTP_202_ACCEPTED)
async def like_comment(
    comment_id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)
):
    try:
        # Проверяем существование комментария
        comment = await db.execute(
            select(Comment).where(Comment.id == comment_id)
        )
        comment = comment.scalar_one_or_none()
        
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found"
            )
        
        # Проверяем, есть ли уже лайк
        existing_like = await db.execute(
            select(CommentsLikes).where(
                CommentsLikes.user_id == user.id,
                CommentsLikes.comment_id == comment_id
            )
        )
        existing_like = existing_like.scalar_one_or_none()
        
        if existing_like:
            # Удаляем лайк
            comment.like_count -= 1
            await db.delete(existing_like)
            await db.commit()
            return {"liked": False, "like_count": comment.like_count}
        else:
            # Добавляем лайк
            new_like = CommentsLikes(user_id=user.id, comment_id=comment_id)
            db.add(new_like)
            comment.like_count += 1
            await db.commit()
            return {"liked": True, "like_count": comment.like_count}
            
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error when trying to like comment: {e}"
        )