from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from typing import Annotated, Dict, Any
from datetime import timedelta

from config.appsettings import Settings
from config.database import get_db
from models.users import Users
from schemas.auth import Token, TokenData, LoginRequest, Tokens
from schemas.user import UserCreate, UserVerified, UserVerify
from services.AuthService import AuthService

router = APIRouter(
    prefix='/auth',
    tags=['authentication']
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/login')

@router.post('/register', status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):

    try:
        exisisting_email = await AuthService.get_user_by_email(db, user_data.email)
        if exisisting_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='User with this email already exists'
            )
        
        exisisting_nickname = await AuthService.get_user_by_nickname(db, user_data.nickname)
        if exisisting_nickname:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='User with this nickname already exists'
            )
        
        hashed_password = AuthService.get_password_hash(user_data.password)

        verification_code = AuthService.generate_verification_code()

        #TODO Добавить отправку кода

        new_user = Users(
            email=user_data.email,
            nickname=user_data.nickname,
            password=hashed_password, 
            verification_code=verification_code
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return {'message': 'User successfully created'}
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Server error occured. Registration failed: {e}'
        )

@router.post('/verify', status_code=status.HTTP_202_ACCEPTED)
async def verify(user_data: UserVerify, db: AsyncSession = Depends(get_db)):
    try:
        user = await AuthService.get_user_by_email(db, user_data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='User not found'
            )
        
        if user.verification_code != user_data.verification_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid verification code'
            )
        
        user.is_verified = True
        user.verification_code = None

        await db.commit()
        await db.refresh(user)

        return {'message': 'User successfully verified'}

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Server error occured. User verification failed: {e}'
        )
    
@router.post('/login', response_model=Tokens, status_code=status.HTTP_202_ACCEPTED)
async def login(user_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:

        user = await AuthService.authenticate_user(db=db, user_data=user_data)
        print(f"ID: {user.id}, email: {user.email} ({type(user.email)}), nickname: {user.nickname} ({type(user.nickname)})")
        print(f"user_data.password: {user_data.password}")
        token_data = TokenData(
            sub=str(user.id),
            email=user.email,
            nickname=user.nickname
        )

        access_token = AuthService.create_jwt_token(token_data, 'access')
        refresh_token = AuthService.create_jwt_token(token_data, 'refresh')

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": 'bearer'}
    
    except Exception as e:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Login error occured: {e}'
        )



        
        
        

        

        
