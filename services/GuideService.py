import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.guides import Guides
from models.users import Users
from fastapi import HTTPException



class GuideService:

    @staticmethod
    def sanitize_folder_name(title: str, timestamp: str) -> str:
        safe_title = re.sub(r'[\W]+', '_', title).strip('_')

        return f"{safe_title}_{timestamp}"
    
    @staticmethod
    def save_markdown_file(folder_path: Path, markdown_text: str, filename: str = "guide.md") -> Path:
        md_path = folder_path / filename
        folder_path.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown_text, encoding="utf-8")

        return md_path
    
    @staticmethod
    def save_logo_file(folder_path: Path, logo_file, filename_prefix: str = "logo") -> Path:
        logo_filename = f"{filename_prefix}_{logo_file.filename}"
        logo_path = folder_path / logo_filename
        with open(logo_path, "wb") as out_logo:
            shutil.copyfileobj(logo_file.file, out_logo)

        return logo_path
    
    @staticmethod
    def validate_path_within_content_dir(path: Path, base_dir: Path) -> bool:
        try:
            return str(path.resolve()).startswith(str(base_dir.resolve()))
        except Exception:
            return False
        
    async def get_guide_by_id(db: AsyncSession, guide_id: int, user: Users = None) -> Guides | None:
        try:
            stmt = select(Guides).where(Guides.id == guide_id)
            if user:
                stmt = stmt.where(Guides.author_id == user.id)
            result = await db.execute(stmt)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f'Error getting guide by id: {e}'
            )

        return result.scalar_one_or_none()
