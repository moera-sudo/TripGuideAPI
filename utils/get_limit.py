from sqlalchemy import func, select
from services.AuthService import AuthService
from config.database import get_db
from models.users import Users
from models.guides import Guides

from typing import Annotated
from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession


async def get_limit(db: AsyncSession = Depends(get_db)) -> int:
    try:
        result = await db.execute(select(func.count(Guides.id)))  
        count = result.scalar()

        limit = count // 2

        return limit
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error getting limit: {e}'
        )
        