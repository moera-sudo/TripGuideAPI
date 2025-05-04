import os
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
from models.comments import Comment
from models.commentslikes import CommentsLikes
from schemas.guides import GuideBase
from models.guideslikes import GuideLikes
from models.guidetags import GuideTags
from utils.current_user import get_current_user
from utils.comments import build_comment_tree
from utils.recommendation_service import get_recommendation_service
from services.RecommendationService import RecommendationService
from services.GuideService import GuideService


router = APIRouter(
    prefix='/guide',
    tags=['guide']
)


    
@router.post('/guide_image', status_code=status.HTTP_202_ACCEPTED)
async def upload_guide_image(file : UploadFile = File(...)):
    try:
        files = {
            "fileToUpload": (file.filename, await file.read(), file.content_type)
        }

        data = {
            "reqtype": "fileupload",
            "userhash": Settings.CATBOX_USERHASH
        }

        async with httpx.AsyncClient() as client:
            response = await client.post("https://catbox.moe/user/api.php", data=data, files=files)

        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload to Catbox")

        return {"image_url": response.text.strip()}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Catbox upload failed: {e}")

    # http://localhost/guide/get_guide_logo/{id}
@router.get('/get_guide_logo/{guide_id}', response_class=FileResponse,  status_code=status.HTTP_200_OK)
async def get_guide_logo(guide_id: int, db: AsyncSession = Depends(get_db)):
    try:
        guide = await GuideService.get_guide_by_id(db, guide_id)


        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Guide not found'
            )
        
        logo_path = guide.head_image_url

        #! Нету проверки на существование лого - могут быть ошибки
        
        headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
        }

        return FileResponse(logo_path, headers=headers)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving logo: {str(e)}"
        )


# @router.post("/save_guide", status_code=status.HTTP_201_CREATED)
# async def save_guide(
#     data: GuideBase,
#     logo: UploadFile = File(...),
#     tags: List[str] = Form(...),
#     db: AsyncSession = Depends(get_db),
#     user: Users = Depends(get_current_user),
# ):
#     try:
#         # ! Потестить, потом удалить
#         # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         # safe_title = re.sub(r'[^\w\s-]', '_', data.title) #* Добавлено изменение имени папки для безопасности. 
#         # guide_folder_name = f"{safe_title}_{timestamp}".replace(" ", "_")
#         # guide_path = content_dir / guide_folder_name
#         # guide_path.mkdir(parents=True, exist_ok=True)

#         # md_filename = "guide.md"
#         # md_path = guide_path / md_filename
#         # async with aiofiles.open(md_path, "w", encoding="utf-8") as f:
#         #     await f.write(data.markdown_text)

#         # logo_filename = f"logo_{logo.filename}"
#         # logo_path = guide_path / logo_filename
#         # with open(logo_path, "wb") as out_logo:
#         #     shutil.copyfileobj(logo.file, out_logo)
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         guide_folder_name = GuideService.sanitize_folder_name(data.title, timestamp)
#         guide_path = content_dir / guide_folder_name
        
#         md_path = GuideService.save_markdown_file(guide_path, data.markdown_text)
#         logo_path = GuideService.save_logo_file(guide_path, logo)

#         guide = Guides(
#             title=data.title,
#             description=data.description,
#             content_file_url=str(md_path),
#             head_image_url=str(logo_path),
#             author_id=user.id
#         )
#         db.add(guide)
#         await db.flush()

#         tag_objects = []
#         for tag_name in tags:
#             tag_name = tag_name.strip()
#             tag_query = await db.execute(select(Tags).where(Tags.name == tag_name))
#             tag = tag_query.scalar_one_or_none()
#             if not tag:
#                 tag = Tags(name=tag_name)
#                 db.add(tag)
#                 await db.flush()
#             tag_objects.append(tag)

#         # Создание связей в guide_tags
#         for tag in tag_objects:
#             link = GuideTags(guide_id=guide.id, tag_id=tag.id)
#             db.add(link)

#         await db.commit()


#         return {"message": "Guide saved successfully"}

#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error while saving guide: {e}"
#         )

@router.post("/save_guide", status_code=status.HTTP_201_CREATED)
async def save_guide(
    data: GuideBase = Depends(GuideBase.as_form),
    logo: UploadFile = File(...),
    tags: List[str] = Form(...),
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(get_current_user),
    recommendation_service: RecommendationService = Depends(get_recommendation_service)
):
    try:
        # Создание папки и сохранение файлов
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        guide_folder_name = GuideService.sanitize_folder_name(data.title, timestamp)
        guide_path = content_dir / guide_folder_name
        
        md_path = GuideService.save_markdown_file(guide_path, data.markdown_text)
        logo_path = GuideService.save_logo_file(guide_path, logo)

        # Создание путеводителя
        guide = Guides(
            title=data.title,
            description=data.description,
            content_file_url=str(md_path),
            head_image_url=str(logo_path),
            author_id=user.id
        )
        db.add(guide)
        await db.flush()  # Получаем ID guide

        # Обработка тегов
        tag_objects = []
        for tag_name in tags:
            tag_name = tag_name.strip()
            tag = await db.scalar(select(Tags).where(Tags.name == tag_name))
            if not tag:
                tag = Tags(name=tag_name)
                db.add(tag)
                await db.flush()
            tag_objects.append(tag)

        # Связи с тегами
        db.add_all([
            GuideTags(guide_id=guide.id, tag_id=tag.id) 
            for tag in tag_objects
        ])

        await db.commit()

        # Индексация нового путеводителя (после коммита)
        try:
            # Явно загружаем теги для индексации
            await db.refresh(guide)
            guide.tags = tag_objects
            
            await recommendation_service.index_guide(guide)
        except Exception as e:
            logger.error(f"Failed to index guide {guide.id}: {e}")
            # Не прерываем выполнение, т.к. основное сохранение прошло успешно

        return {
            "message": "Guide saved successfully",
            "guide_id": guide.id
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error while saving guide"
        )

@router.put('/edit/{guide_id}', status_code=status.HTTP_202_ACCEPTED)
async def edit_guide(
    guide_id: int,
    data: GuideBase = Depends(GuideBase.as_form),
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(get_current_user)):
    
    try:
        guide = await GuideService.get_guide_by_id(db, guide_id, user)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Editing guide not found or not owned by user'
            )
        
        
        if data.markdown_text is not None:
            try:
                with open(guide.content_file_url, 'w', encoding='utf-8') as md_file:
                    md_file.write(data.markdown_text)
            
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f'Failed to update guide: {e}'
                )
            
        if data.title:
            guide.title = data.title
        if data.description:
            guide.description = data.description


        await db.commit()
        await db.refresh(guide)

        return {"message": "Guide updated successfully"}
            
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while editing guide: {e}"
        )
            
@router.delete("/delete/{guide_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_guide(guide_id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)):
    try:
        guide = await GuideService.get_guide_by_id(db, guide_id, user)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Deleting guide not found or not owned by user'
            )
        
        await db.execute(
            delete(GuideLikes).where(GuideLikes.guide_id == guide_id)
        )
        await db.execute(
            delete(GuideTags).where(GuideTags.guide_id == guide_id)
        )
        
        content_path = os.path.dirname(guide.content_file_url)

        if os.path.exists(content_path):
            shutil.rmtree(content_path)

        await db.delete(guide)

        await db.execute(
            delete(Tags).where(
                ~exists().where(GuideTags.tag_id == Tags.id)
            )
        ) 

        await db.commit()

        return{"message": "Guide deleted successfully"} 

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error while deleting guide: {e}'
        )  
@router.get("/read_guide/{guide_id}", status_code=status.HTTP_200_OK)
async def read_guide(guide_id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)):
    try:
        result = await db.execute(
            select(Guides)
            .where(Guides.id == guide_id)
            .options(
                selectinload(Guides.author),
                selectinload(Guides.tags),
                selectinload(Guides.comments)
                    .selectinload(Comment.author),  # автор комментария
                selectinload(Guides.comments)
                    .selectinload(Comment.liked_by),  # лайки на комментарии
                selectinload(Guides.comments)
                    .selectinload(Comment.replies)  # ответы на комментарии
            )
        )
        guide = result.scalar_one_or_none()

        if not guide:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guide not found")
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error while reading guide: {e}'
        )
    else:

        try:
            md_path = Path(guide.content_file_url)
            async with aiofiles.open(md_path, mode="r", encoding="utf-8") as f:
                markdown_text = await f.read()

            is_liked = False

            if user:
                result = await db.execute(
                    select(GuideLikes).where(
                        GuideLikes.user_id == user.id,
                        GuideLikes.guide_id == guide.id
                    )
                )
                is_liked = result.scalar_one_or_none() is not None

            discussion = [
                build_comment_tree(comment, user.id if user else None)
                for comment in sorted(
                    [c for c in guide.comments if c.parent_id is None],
                    key=lambda x: x.created_at,
                    reverse=True
                )
            ]

            return {
                "guide": {
                    "title": guide.title,
                    "description": guide.description,
                    "markdown_text": markdown_text,
                    "author": guide.author.nickname,
                    "liked_by_user": is_liked,
                    "likes_count": guide.like_count,
                    "tags": [tag.name for tag in guide.tags],
                    "created_at": guide.created_at
                },
                "discussion":discussion
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error reading guide file: {e}"
            )

@router.post('/like/{guide_id}', status_code=status.HTTP_202_ACCEPTED)
async def like_guide(guide_id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)):
    try:
        result = await db.execute(
            select(GuideLikes).where(GuideLikes.user_id == user.id, GuideLikes.guide_id == guide_id)
        )
        existing = result.scalar_one_or_none()

        guide = await GuideService.get_guide_by_id(db, guide_id)

        
        if guide:
            if existing:
                guide.like_count-= 1
                await db.delete(existing)
                await db.commit()
                return {"liked": False}
            else:
                like = GuideLikes(user_id=user.id, guide_id=guide.id)
                db.add(like)
                guide.like_count+= 1
                await db.commit()
                return {"liked": True}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error when trying to like: {e}"
        )
   
@router.get("/tags", status_code=status.HTTP_200_OK)
async def get_tags(db: AsyncSession = Depends(get_db)):
    try: #Возвращает все уникальные теги
        tags_result = await db.execute(select(Tags.name).distinct())
        all_tags = [row.name for row in tags_result.fetchall()]

        return {"tags": all_tags}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while extraction tags: {e}"
        )