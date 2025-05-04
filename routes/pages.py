from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from models.guideslikes import GuideLikes
from models.users import Users
from models.guides import Guides
from models.tags import Tags
from utils.current_user import get_current_user
from utils.recommendation_service import get_recommendation_service
from utils.get_limit import get_limit
from services.RecommendationService import RecommendationService

router = APIRouter(
    tags=['pages']
)


# TODO Тут короче будут роуты для того чтобы выводить на фронт карточки путеводителей. Надо для рекомендаций, каталога, главной и профиля

@router.get('/catalog', status_code=status.HTTP_200_OK)
async def get_catalog(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Guides)
            .options(
                selectinload(Guides.tags),
            )
            .order_by(Guides.created_at.desc())
        )
        guides = result.scalars().all()

        # Получаем все уникальные теги
        tags_result = await db.execute(select(Tags.name).distinct())
        all_tags = [row.name for row in tags_result.fetchall()]

        return {
            "guides": [
                {
                    "id": guide.id,
                    "title": guide.title,
                    "description": guide.description,
                    "guide_tags": [tag.name for tag in guide.tags]
                }
                for guide in guides
            ],
            "tags": all_tags
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting catalog: {e}"
        )

@router.get('/popular', status_code=status.HTTP_200_OK)
async def get_popular(db: AsyncSession = Depends(get_db)):
    try:

        result = await db.execute(
            select(Guides)
            .options(
                selectinload(Guides.tags)
            )
            .order_by(Guides.like_count.desc()).limit(3)
        )
        guides = result.scalars().all()

        return {
            "guides": [
                {
                    "id": guide.id,
                    "title": guide.title,
                    "description" : guide.description,
                    "author": guide.author.nickname,
                    "created_at": guide.created_at,
                    "guide_tags": [tag.name for tag in guide.tags]
                }
                for guide in guides
            ]
        } 
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting popular: {e}"
        )

@router.get('/profile', status_code=status.HTTP_200_OK)
async def get_profile(db: AsyncSession = Depends(get_db), user: Users = Depends(get_current_user)):
    try:

        result = await db.execute(
            select(Guides).where(Guides.author_id == user.id).options(selectinload(Guides.tags)).order_by(Guides.created_at.desc())
        )
        guides = result.scalars().all()

        result = await db.execute(
            select(Guides)
            .join(GuideLikes, GuideLikes.guide_id == Guides.id)
            .where(GuideLikes.user_id == user.id)
            .options(selectinload(Guides.tags))

        )
        liked_guides = result.scalars().all()


        return {
            "guides": [
                {
                    "id": guide.id,
                    "title": guide.title,
                    "description": guide.description,
                    "created_at": guide.created_at,
                    "tags": [tag.name for tag in guide.tags]

                }
                for guide in guides   
            ],
            "liked_guides": [
                {
                    "id": guide.id,
                    "title": guide.title,
                    "description": guide.description,
                    "created_at": guide.created_at,
                    "tags": [tag.name for tag in guide.tags]

                }
                for guide in liked_guides
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting profile: {e}"
        )

# ! надо потестить йоу
@router.get("/recs", status_code=status.HTTP_200_OK)
async def get_recommendations(
    limit: int = Depends(get_limit), 
    db: AsyncSession = Depends(get_db), 
    user: Users = Depends(get_current_user),
    recommendation_service: RecommendationService = Depends(get_recommendation_service)
):
    """
    Получение персонализированных рекомендаций для авторизованного пользователя
    Возвращает:
    - recommendations: список рекомендованных путеводителей с их тегами
    """
    try:
        # Получаем рекомендации через сервис
        guide_ids = await recommendation_service.get_user_recommendations(
            db=db,
            user_id=user.id,
            limit=limit
        )
        
        if not guide_ids:
            return {"recommendations": []}
        
        # Получаем полную информацию о путеводителях одним запросом
        stmt = (
            select(Guides)
            .where(Guides.id.in_(guide_ids))
            .options(selectinload(Guides.tags))
        )
        result = await db.execute(stmt)
        guides = result.scalars().all()
        
        # Создаем словарь для быстрого доступа по ID
        guides_dict = {guide.id: guide for guide in guides}
        
        # Формируем ответ, сохраняя порядок рекомендаций
        recommendations = []
        for guide_id in guide_ids:
            guide = guides_dict.get(guide_id)
            if guide:
                recommendations.append({
                    "id": guide.id,
                    "title": guide.title,
                    "description": guide.description,
                    "tags": [tag.name for tag in guide.tags],
                    "created_at": guide.created_at,
                    "like_count": guide.like_count
                })
        
        return {"recommendations": recommendations}
    
    except HTTPException:
        raise
    except Exception as e:
        # logger.error(f"Recommendation error for user {user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось получить рекомендации"
        )
