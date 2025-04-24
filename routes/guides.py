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
from config.config import content_dir
from models.users import Users
from models.guides import Guides
from models.tags import Tags
from models.guideslikes import GuideLikes
from models.guidetags import GuideTags
from services.AuthService import AuthService

router = APIRouter(
    prefix='/guide',
    tags=['guide']
)


# TODO Надо сделать маршрут для редактирования


    
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
        stmt = select(Guides).where(Guides.id == guide_id)
        result = await db.execute(stmt)
        guide = result.scalars().first()

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Guide not found'
            )
        
        logo_path = guide.head_image_url

        # if not logo_path.exists():
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail="Head image not found"
        #     )

        
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



@router.post("/save_guide", status_code=status.HTTP_201_CREATED)
async def save_guide(
    title: str = Form(...),
    description: str = Form(...),
    markdown_text: str = Form(...),
    logo: UploadFile = File(...),
    tags: List[str] = Form(...),
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(AuthService.get_current_user),
):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        guide_folder_name = f"{title}_{timestamp}".replace(" ", "_")
        guide_path = content_dir / guide_folder_name
        guide_path.mkdir(parents=True, exist_ok=True)

        md_filename = "guide.md"
        md_path = guide_path / md_filename
        async with aiofiles.open(md_path, "w", encoding="utf-8") as f:
            await f.write(markdown_text)

        logo_filename = f"logo_{logo.filename}"
        logo_path = guide_path / logo_filename
        with open(logo_path, "wb") as out_logo:
            shutil.copyfileobj(logo.file, out_logo)

        guide = Guides(
            title=title,
            description=description,
            content_file_url=str(md_path),
            head_image_url=str(logo_path),
            author_id=user.id
        )
        db.add(guide)
        await db.flush()

        tag_objects = []
        for tag_name in tags:
            tag_name = tag_name.strip().lower()
            tag_query = await db.execute(select(Tags).where(Tags.name == tag_name))
            tag = tag_query.scalar_one_or_none()
            if not tag:
                tag = Tags(name=tag_name)
                db.add(tag)
                await db.flush()
            tag_objects.append(tag)

        # Создание связей в guide_tags
        for tag in tag_objects:
            link = GuideTags(guide_id=guide.id, tag_id=tag.id)
            db.add(link)

        await db.commit()


        return {"message": "Guide saved successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while saving guide: {e}"
        )
    
@router.get("/read_guide/{guide_id}", status_code=status.HTTP_200_OK)
async def read_guide(guide_id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(AuthService.get_current_user)):

    result = await db.execute(
        select(Guides).where(Guides.id == guide_id).options(selectinload(Guides.author), selectinload(Guides.tags))
    )
    guide = result.scalar_one_or_none()

    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")

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


        return {
            "title": guide.title,
            "description": guide.description,
            "markdown_text": markdown_text,
            "author": guide.author.nickname,
            "liked_by_user": is_liked,
            "likes_count": guide.like_count,
            "tags": [tag.name for tag in guide.tags],
            "created_at": guide.created_at
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading guide file: {e}"
        )

# @router.post("/guides/{guide_id}/like", status_code=status.HTTP_200_OK)
# async def like_guide(
#     guide_id: int,
#     db: AsyncSession = Depends(get_db),
#     user: Users = Depends(AuthService.get_current_user)
# ):
#     result = await db.execute(
#         select(GuideLikes).where(
#             GuideLikes.user_id == user.id,
#             GuideLikes.guide_id == guide_id
#         )
#     )
#     existing = result.scalar_one_or_none()

#     if existing:
#         # Убираем лайк
#         await db.delete(existing)
#         await db.commit()
#         return {"liked": False}

#     # Добавляем лайк
#     like = GuideLikes(user_id=user.id, guide_id=guide_id)
#     db.add(like)

#     # Увеличиваем счетчик лайков
#     result = await db.execute(select(Guides).where(Guides.id == guide_id))
#     guide = result.scalar_one_or_none()
#     if guide:
#         guide.like_count += 1

#     await db.commit()
#     return {"liked": True}

@router.post('/like/{guide_id}', status_code=status.HTTP_202_ACCEPTED)
async def like_guide(guide_id: int, db: AsyncSession = Depends(get_db), user: Users = Depends(AuthService.get_current_user)):
    try:
        result = await db.execute(
            select(GuideLikes).where(GuideLikes.user_id == user.id, GuideLikes.guide_id == guide_id)
        )
        existing = result.scalar_one_or_none()
        guide_response = await db.execute(select(Guides).where(Guides.id == guide_id))
        guide = guide_response.scalar_one_or_none()
        
        if guide:
            if existing:
                guide.like_count=-1
                await db.delete(existing)
                await db.commit()
                return {"liked": False}
            else:
                like = GuideLikes(user_id=user.id, guide_id=guide.id)
                db.add(like)
                guide.like_count=+1
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

            




#TODO надо потестить теги, мб че то добавить -> сделать рексервис и выгрузку на странички. 