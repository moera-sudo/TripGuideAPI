from config.appsettings import Settings
from config.database import get_db
from models.users import Users
from schemas.auth import TokenData

from passlib.context import CryptContext
from jose import JWTError, jwt, ExpiredSignatureError
from typing import Optional, Annotated, List
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
from datetime import timedelta, datetime
import secrets
import string
import logging

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/login')


class AuthService:



    pwdContext = CryptContext(schemes=["bcrypt"], deprecated="auto")


    @staticmethod
    def get_password_hash(password: str) -> str:
        return AuthService.pwdContext.hash(password)
    
    @staticmethod
    def verify_password(password, hashed_password) -> bool:
        return AuthService.pwdContext.verify(password, hashed_password)

    @staticmethod
    def generate_verification_code(length=6) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def create_jwt_token(token_data: TokenData, token_type: str, expires_delta: Optional[timedelta] = None) -> str:
        
        if not token_data.email and not token_data.nickname:
            raise HTTPException(
                status_code=400,
                detail='Incorrect token data'
            )

        if token_type not in ['refresh', 'access']:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid Token Type'
            )        

        to_encode = token_data.dict()
        now = datetime.utcnow()



        if token_type == 'refresh':
            expire = now + timedelta(days=Settings.REFRESH_TOKEN_EXPIRE_DAYS)
        elif token_type == 'access' and expires_delta:
            expire = now + expires_delta
        elif token_type == 'access' and not expires_delta:
            expire = now + timedelta(minutes=Settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        try:
            
            to_encode.update({
                'exp': expire,
                'iat': now,
                'token_type': 'access' if token_type == 'access' else 'refresh'
            })

            secret_key = Settings.SECRET_KEY if token_type == 'access' else Settings.REFRESH_SECRET_KEY

            encoded_jwt = jwt.encode(
                to_encode,
                secret_key,
                algorithm=Settings.ALGORITHM              
            )
            
            return encoded_jwt
        except(JWTError, ValidationError, ValueError) as e:
            raise HTTPException(
                status_code=500,
                detail=f'Failed to create JWT Token: {e}'
            )

    @staticmethod
    def decode_jwt_token(token: str, token_type: str) -> Optional[TokenData]:
        
        if token_type not in ['refresh', 'access']:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid Token Type'
            ) 
        
        try:
            secret_key = Settings.SECRET_KEY if token_type == 'access' else Settings.REFRESH_SECRET_KEY
            

            payload = jwt.decode(
                token,
                secret_key,
                algorithms=Settings.ALGORITHM
            )

            if payload.get('token_type') != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Inappropriate token type. Expected '{token_type}', got '{payload.get('token_type')}'"
                )
            
            token_data = TokenData(**payload)
            
            return token_data
        
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f'Token expired'
            )
        
        except (JWTError, ValidationError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f'Invalid token: {e}'
            )
    
    # Поидее использовать эту функцию для возвращения User'а предпочтительнее всего
    @staticmethod
    async def get_user_by_id(db: AsyncSession, id=int):
        try:
            return await db.get(Users, id)
        except SQLAlchemyError as e:
            logger.error(f"Database error when getting user by id: {e}")
            raise HTTPException(
                status_code=500,
                detail=f'Database error occured: {e}'
            )
        
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str):
        try:
            stmt = select(Users).where(Users.email == email)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            return user
        except SQLAlchemyError as e:
            logger.error(f"Database error when getting user by email: {e}")
            raise HTTPException(
                status_code=500,
                detail='Database error occurred'
            )
        
    @staticmethod
    async def get_user_by_nickname(db: AsyncSession, nickname: str):
        try:
            stmt = select(Users).where(Users.nickname == nickname)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            return user
        except SQLAlchemyError as e:
            logger.error(f"Database error when getting user by nickname: {e}")
            raise HTTPException(
                status_code=500,
                detail='Database error occurred'
            )
    
    
    @staticmethod
    async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)) -> Users:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        # * надо проверить функцию
        try:
            token_data = AuthService.decode_jwt_token(token, "access")
            if token_data is None:
                raise credentials_exception
            
            user = await AuthService.get_user_by_id(db, token_data.sub)
            if user is None:
                raise credentials_exception
            return user
        except Exception:
            raise credentials_exception
        
    @staticmethod
    async def authenticate_user(db: AsyncSession, user_data):
        try:
            user = None
            
            if user_data.email:
                user = await AuthService.get_user_by_email(db, user_data.email)
            
            if user_data.nickname:
                user = await AuthService.get_user_by_nickname(db, user_data.nickname)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='User not found'
                )
            
            if not user.is_verified:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail='User not verified'
                ) 
            
            if not AuthService.verify_password(user_data.password, user.password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail='Incorrect password'
                    )
            
            return user
        
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f'Authentification error occured: {e}'
            )