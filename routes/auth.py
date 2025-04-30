from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta, datetime

from config.appsettings import Settings
from config.database import get_db
from models.users import Users
from models.refreshtokens import RefreshTokens
from schemas.auth import Token, TokenData, LoginRequest, Tokens
from schemas.user import UserCreate, UserVerify
from services.AuthService import AuthService
from services.EmailService import EmailService
from utils.current_user import get_current_user

router = APIRouter(
    prefix='/auth',
    tags=['authentication']
)

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

        await EmailService.send_verification_email(user_data.email, verification_code)

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
        # * Чуть колхоз, надо добавить отдельную таблицу для верификаций.
        if user.is_verified:
            user.permission_to_recovery = True
        else:
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
        token_data = TokenData(
            sub=str(user.id),
            email=user.email,
            nickname=user.nickname
        )

        access_token = AuthService.create_jwt_token(token_data, 'access')
        refresh_token = AuthService.create_jwt_token(token_data, 'refresh')

        hashed_refresh_token = AuthService.get_password_hash(refresh_token)

        refresh_token_expire = datetime.utcnow() + timedelta(days=Settings.REFRESH_TOKEN_EXPIRE_DAYS)


        RefreshTokenDatabase = RefreshTokens(
            token = hashed_refresh_token,
            user_id = user.id,
            expires_at = refresh_token_expire
        )
        db.add(RefreshTokenDatabase)
        
        await db.commit()
        await db.refresh(RefreshTokenDatabase)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": 'bearer'}
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Login error occured: {e}'
        )



@router.post('/refresh', response_model=Tokens, status_code=status.HTTP_200_OK)
async def refresh_token(token: Token, db: AsyncSession = Depends(get_db)):
    try:
        refresh_token = token.token
        # Декодируем и проверяем тип токена
        token_data = AuthService.decode_jwt_token(refresh_token, 'refresh')

        # Получаем пользователя
        user = await AuthService.get_user_by_id(db, int(token_data.sub))
        if not user:
            raise HTTPException(status_code=404, detail='User not found')

        # Ищем среди токенов совпадение по хэшу
        stmt = select(RefreshTokens).where(
            RefreshTokens.user_id == user.id,
            RefreshTokens.is_revoked == False
        )
        result = await db.execute(stmt)
        active_tokens = result.scalars().all()

        matched_token = next(
            (
                t for t in active_tokens
                if AuthService.verify_password(refresh_token, t.token) and t.is_valid
            ),
            None
        )


        if not matched_token:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        # Ревокация старого токена
        matched_token.is_revoked = True
        matched_token.revoked_at = datetime.utcnow()

        # Создаём новые токены
        access_token = AuthService.create_jwt_token(token_data, 'access')
        new_refresh_token = AuthService.create_jwt_token(token_data, 'refresh')
        hashed_refresh_token = AuthService.get_password_hash(new_refresh_token)

        # Сохраняем новый refresh token
        expires_at = datetime.utcnow() + timedelta(days=Settings.REFRESH_TOKEN_EXPIRE_DAYS)
        new_token_entry = RefreshTokens(
            token=hashed_refresh_token,
            user_id=user.id,
            expires_at=expires_at
        )
        db.add(new_token_entry)

        await db.commit()
        await db.refresh(new_token_entry)

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Refresh token error: {e}"
        )

# TODO Добавить роут восстановления пароля
@router.post('/recovery', status_code=status.HTTP_202_ACCEPTED)
async def password_recovery(email: str, db: AsyncSession = Depends(get_db)):
        # Принимается почта -> Проверка на существование в базе -> отправка кода на сброс -> принимается код -> принимается новый пароль
    try:
        user = await AuthService.get_user_by_email(db=db, email=email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User email not found"
            )
        verification_code = AuthService.generate_verification_code()


        user.verification_code = verification_code

        await EmailService.send_password_recovery_email(email=email, code=verification_code)

        await db.commit()

        return {"message":"Password recovery message sent to email"}
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending verification code: {e}"
        )
    
@router.post('/change_password', status_code=status.HTTP_202_ACCEPTED)
async def change_password(user_data = UserCreate, db : AsyncSession = Depends(get_db)):
    try:
        user = await AuthService.get_user_by_email(db=db, email=user_data.email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User email not found"
            )
        if not user.permission_to_recovery:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Password update forbidden"
            )
        
        new_password = AuthService.get_password_hash(user_data.password)
        user.password = new_password
        user.permission_to_recovery = False


        await db.commit()
        
        return {"message" : "User password updated"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating password"
        )


@router.post('/logout', status_code=status.HTTP_202_ACCEPTED)
async def logout(user: Users = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        # Найти все активные токены пользователя
        stmt = select(RefreshTokens).where(
            RefreshTokens.user_id == user.id,
            RefreshTokens.is_revoked == False
        )
        result = await db.execute(stmt)
        active_tokens = result.scalars().all()
        
        # Отозвать все активные токены
        current_time = datetime.utcnow()
        for token in active_tokens:
            token.is_revoked = True
            token.revoked_at = current_time
        
        await db.commit()
        
        return {"message": "Log out successful"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Log out error: {str(e)}"
        )