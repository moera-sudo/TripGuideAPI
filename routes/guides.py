import shutil
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
from config.config import uploads_dir, content_dir
from models.users import Users
from models.guides import Guides
from schemas.user import UserInfo
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
    db: AsyncSession = Depends(get_db),
    user: Users = Depends(AuthService.get_current_user),
):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        guide_folder_name = f"{title}_{timestamp}".replace(" ", "_")
        guide_path = content_dir / guide_folder_name
        guide_path.mkdir(parents=True, exist_ok=True)

        # Save markdown text to file
        md_filename = "guide.md"
        md_path = guide_path / md_filename
        async with aiofiles.open(md_path, "w", encoding="utf-8") as f:
            await f.write(markdown_text)

        # Save logo
        logo_filename = f"logo_{logo.filename}"
        logo_path = guide_path / logo_filename
        with open(logo_path, "wb") as out_logo:
            shutil.copyfileobj(logo.file, out_logo)

        # Save to DB
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
    
@router.get("/read_guide/{guide_id}", status_code=status.HTTP_200_OK)
async def read_guide(guide_id: int, db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        select(Guides).where(Guides.id == guide_id).options(selectinload(Guides.author))
    )
    guide = result.scalar_one_or_none()

    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")

    try:
        md_path = Path(guide.content_file_url)
        async with aiofiles.open(md_path, mode="r", encoding="utf-8") as f:
            markdown_text = await f.read()

        return {
            "title": guide.title,
            "description": guide.description,
            "logo_url": f"http://127.0.0.1:8000/guide/get_guide_logo/{guide.id}",
            "markdown_text": markdown_text,
            "author": guide.author.nickname,
            "author_avatar": f"http://127.0.0.1:8000/user/avatar/{guide.author.nickname}", 
            # ! Эта штука тестовая, я хз сработает ли
            "created_at": guide.created_at
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading guide file: {e}"
        )



#TODO сука надо эту хуйню доделать+странички(хотя бы каталог)+теги+реки. я не ебу как я вам теги сделаю, потому что там ебли с реактом даже больше будет