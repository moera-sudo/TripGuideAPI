import shutil
from typing import List
import httpx
import aiofiles
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config.appsettings import Settings
from config.database import get_db
from config.config import uploads_dir, content_dir
from models.guideslikes import GuideLikes
from models.users import Users
from models.guides import Guides
from models.tags import Tags
from models.guidetags import GuideTags
from schemas.user import UserInfo
from services.AuthService import AuthService
from services.RecommendationService import RecommendationService

router = APIRouter(
    tags=['pages']
)


# TODO Тут короче будут роуты для того чтобы выводить на фронт карточки путеводителей. Надо для рекомендаций, каталога, главной и профиля

@router.get('/catalog', status_code=status.HTTP_200_OK)
async def get_catalog(db: AsyncSession = Depends(get_db)):
    
    result = await db.execute(
        select(Guides)
        .options(
            selectinload(Guides.tags),
        )
        .order_by(Guides.created_at.desc())
    )
    guides = result.scalars().all()

    # Получаем все уникальные теги
    tags_result = await db.execute(select(Tags.name).distinct())
    all_tags = [row.name for row in tags_result.fetchall()]

    return {
        "guides": [
            {
                "id": guide.id,
                "title": guide.title,
                "description": guide.description,
                "guide_tags": [tag.name for tag in guide.tags]
            }
            for guide in guides
        ],
        "tags": all_tags
    }

@router.get('/popular', status_code=status.HTTP_200_OK)
async def get_popular(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Guides)
        .options(
            selectinload(Guides.tags)
        )
        .order_by(Guides.like_count.desc()).limit(3)
    )
    guides = result.scalars().all()

    # id, title, description, author, created_at
    return {
        "guides": [
            {
                "id": guide.id,
                "title": guide.title,
                "description" : guide.description,
                "author": guide.author.nickname,
                "created_at": guide.created_at,
                "guide_tags": [tag.name for tag in guide.tags]
            }
            for guide in guides
        ]
    } 

@router.get('/profile', status_code=status.HTTP_200_OK)
async def get_profile(db: AsyncSession = Depends(get_db), user: Users = Depends(AuthService.get_current_user)):
    result = await db.execute(
        select(Guides).where(Guides.author_id == user.id).options(selectinload(Guides.tags)).order_by(Guides.created_at.desc())
    )
    guides = result.scalars().all()

    result = await db.execute(
        select(Guides)
        .join(GuideLikes, GuideLikes.guide_id == Guides.id)
        .where(GuideLikes.user_id == user.id)
        .options(selectinload(Guides.tags))

    )
    liked_guides = result.scalars().all()


    return {
        "guides": [
            {
                "id": guide.id,
                "title": guide.title,
                "description": guide.description,
                "created_at": guide.created_at,
                "tags": [tag.name for tag in guide.tags]

            }
            for guide in guides   
        ],
        "liked_guides": [
            {
                "id": guide.id,
                "title": guide.title,
                "description": guide.description,
                "created_at": guide.created_at,
                "tags": [tag.name for tag in guide.tags]

            }
            for guide in liked_guides
        ]
    }

# ! надо потестить йоу
@router.get("/recs", status_code=status.HTTP_200_OK)
async def get_recs(limit: int = 20, db: AsyncSession = Depends(get_db), user: Users = Depends(AuthService.get_current_user)):
    try:
        guides = RecommendationService.get_recommendations_by_user_likes(
            db=db,
            user_id=user.id,
            limit=limit
        )
        if not guides:
            return {"recommendations": []}
        
        stmt = select(Guides).where(Guides.id.in_(guides))
        result = await db.execute(stmt)
        guides = result.scalars().all()
        
        sorted_guides = sorted(guides, key=lambda g: guides.index(g.id))
        
        # Форматируем результат
        recommendations = []
        for guide in sorted_guides:
            recommendations.append({
                "id": guide.id,
                "title": guide.title,
                "description": guide.description,
                "tags": [tag.name for tag in guide.tags]
            })

        return {"recommendations": recommendations}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while getting recommendations: {e}"
        )




"""
Я короче хз как тут щас делать. Надо щас сделать какое то подобие рекомендаций
я хз правильно ли работают лайки но щас их особо не потестишь soooo я пока вслепую напишу....
"""

