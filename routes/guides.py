from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.appsettings import Settings
from config.database import get_db
from config.config import uploads_dir
from models.users import Users
from schemas.user import UserInfo
from services.AuthService import AuthService

router = APIRouter(
    prefix='/guide',
    tags=['guide']
)


# TODO Надо сделать маршрут для 1) Создания, Редактирования, Просмотра

"""
При создании путеводителя должно принимать: Название, описание, head_Image, и md . Также все фотки с него. 
"""

# @router.post()