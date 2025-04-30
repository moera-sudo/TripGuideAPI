from services.AuthService import AuthService
from config.database import get_db
from models.users import Users

from typing import Annotated
from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession



oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/login')



async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)) -> Users:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_data = AuthService.decode_jwt_token(token, "access")
        if token_data is None:
            
            raise credentials_exception
        
        user = await AuthService.get_user_by_id(db, token_data.sub)
        if user is None:
            raise credentials_exception
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unexpected error: {e}",
            headers={"WWW-Authenticate": "Bearer"}
        )