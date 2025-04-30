import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.appsettings import Settings
from config.database import get_db
from config.config import uploads_dir
from models.users import Users
from schemas.user import UserInfo
from utils.current_user import get_current_user

router = APIRouter(
    prefix='/user',
    tags=['user']
)


# Маршрут для обновления информации о пользователе в личном кабе -> настройки
@router.post('/info', status_code=status.HTTP_202_ACCEPTED)
async def load_user_info(
    user_data: UserInfo,
    user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        data = user_data.dict(exclude_unset=True)

        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    value = None  # Пустые строки заменим на None

            # Автоконвертация числовых полей
            if key in ["age", "cof"] and isinstance(value, str) and value.isdigit():
                value = int(value)

            setattr(user, key, value)

        await db.commit()
        return {"message": "User info updated"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"User info update error: {e}"
        )


# Маршрут для получения информации о пользователе в личном кабе -> настройки
@router.get('/get_info', response_model=UserInfo, status_code=status.HTTP_200_OK)
async def get_user_info(user: Users = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try: 
        return{
            'nickname': user.nickname,
            "username": user.username,
            "age": str(user.age),
            "gender": user.gender,
            "about": user.about,
            "cof": str(user.cof),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"User info get error: {e}"
        )

# Маршрут для загрузки изображения аватара пользователя
@router.post('/upload_avatar', status_code=status.HTTP_202_ACCEPTED)
async def upload_avatar(
    file: UploadFile = File(...), 
    user: Users = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    # Проверка типа файла
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Unsupported image type. Only JPEG and PNG are allowed.'
        )
    
    try:
        # Создаем имя файла на основе никнейма пользователя
        filename = f"{user.nickname}_avatar.{file.filename.split('.')[-1]}"
        file_path = uploads_dir / filename
        
        # Сохраняем файл
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Обновляем путь к аватару в базе данных
        user.avatar_url = filename
        await db.commit()
        
        return {"message": "Avatar uploaded successfully", "avatar_url": filename}
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Avatar upload error: {str(e)}"
        )
    
# Маршрут для получения аватарки по нику 
@router.get('/avatar/{nickname}', response_class=FileResponse)
async def get_avatar(nickname: str, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Users).where(Users.nickname == nickname)
        result = await db.execute(stmt)
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        avatar_path = uploads_dir / user.avatar_url

        if not avatar_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Avatar file not found"
            )

        headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
        }
    
        return FileResponse(avatar_path, headers=headers)


    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving avatar: {str(e)}"
        )

#Маршрут для получения аватарки по токену
@router.get('/my_avatar', response_class=FileResponse)
async def get_my_avatar(user: Users = Depends(get_current_user)):
    try:
        avatar_path = uploads_dir / user.avatar_url


        if not avatar_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Avatar file not found"
            )

        return FileResponse(avatar_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving avatar: {str(e)}"
        )
    
@router.delete('/delete_avatar', status_code=status.HTTP_202_ACCEPTED)
async def delete_avatar(user: Users = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        if user.avatar_url != 'default.jpg':
            avatar_path = uploads_dir / user.avatar_url
            os.remove(avatar_path)
            user.avatar_url = 'default.jpg'
            await db.commit()

        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='User do not have avatar'
            )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Avatar deleting error: {e}'
        )

#TODO Тут надо написать роут удаления аккаунта(когда нибудь)