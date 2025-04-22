import shutil
import httpx
import aiofiles
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.appsettings import Settings
from config.database import get_db
from config.config import uploads_dir, content_dir
from models.users import Users
from models.guides import Guides
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

    
# !TODO надо сделать роут загрузки изображений в черновик

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
    


@router.post("/save_guide", status_code=status.HTTP_201_CREATED)
async def save_guide(
    title: str = Form(...),
    description: str = Form(...),
    logo: UploadFile = File(...),
    markdown_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(AuthService.get_current_user)):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        guide_folder_name = f"{title}_{timestamp}".replace(" ", "_")
        guide_path = content_dir / guide_folder_name
        guide_path.mkdir(parents=True, exist_ok=True)

        # Save markdown file
        md_filename = "guide.md"
        md_path = guide_path / md_filename
        async with aiofiles.open(md_path, "wb") as out_md:
            content = await markdown_file.read()
            await out_md.write(content)

        # Save logo
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
        await db.commit()

        return {"message": "Guide saved successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while saving guide: {e}"
        )
    
    