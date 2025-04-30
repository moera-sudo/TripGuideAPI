from fastapi import Form
from pydantic import BaseModel, EmailStr, ConfigDict, model_validator
from typing import Optional

# TODO Надо добавить схемки для создания/редактирования и просмотра. Мб еще на респонс че то

class GuideBase(BaseModel):
    title: str
    description: str
    markdown_text: str

    @classmethod
    def as_form(
        cls,
        title: str = Form(...),
        description: str = Form(...),
        markdown_text: str = Form(...)
    ):
        return cls(title=title, description=description, markdown_text=markdown_text)