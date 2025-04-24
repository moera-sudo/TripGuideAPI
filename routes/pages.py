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
from models.users import Users
from models.guides import Guides
from models.tags import Tags
from models.guidetags import GuideTags
from schemas.user import UserInfo
from services.AuthService import AuthService
# from services.RecommendationService import RecommendationService

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
                "tags": [tag.name for tag in guide.tags]
            }
            for guide in guides
        ],
        "tags": all_tags
    }

# @router.get('/recommendations', status_code=status.HTTP_200_OK)
# async def get_recs(db: AsyncSession = Depends(get_db), user: AsyncSession = Depends(AuthService.get_current_user)):




"""
Я короче хз как тут щас делать. Надо щас сделать какое то подобие рекомендаций
я хз правильно ли работают лайки но щас их особо не потестишь soooo я пока вслепую напишу....
"""

