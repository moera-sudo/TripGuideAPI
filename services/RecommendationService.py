from config.database import get_db
from models.users import Users
from models.guides import Guides
from models.tags import Tags
from models.guidetags import GuideTags
from models.guideslikes import GuideLikes
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import Depends, HTTPException, status
from typing import List, Dict, Set, Optional, Annotated
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import logging
from collections import Counter
import re

logger = logging.getLogger(__name__)

class RecommendationService:
    """Сервис рекомендаций на основе контента (content-based filtering)"""

    model_name = "all-MiniLM-L6-v2"
    collection_name = "guides"
    
    @staticmethod
    def get_embedding_model():
        """Получение модели для создания эмбеддингов"""
        try:
            return SentenceTransformer(RecommendationService.model_name)
        except Exception as e:
            logger.error(f"Error initializing embedding model: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error initializing recommendation service: {e}"
            )
    
    @staticmethod
    def get_chroma_client():
        """Получение клиента ChromaDB"""
        try:
            return chromadb.Client()
        except Exception as e:
            logger.error(f"Error initializing ChromaDB client: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error initializing vector storage"
            )
    
    @staticmethod
    def get_collection():
        """Получение или создание коллекции в ChromaDB"""
        try:
            client = RecommendationService.get_chroma_client()
            model = RecommendationService.get_embedding_model()
            
            embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=RecommendationService.model_name
            )
            
            return client.get_or_create_collection(
                name=RecommendationService.collection_name,
                embedding_function=embedding_function
            )
        except Exception as e:
            logger.error(f"Error creating ChromaDB collection: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error initializing vector collection"
            )

    @staticmethod
    def preprocess_text(text: str) -> str:
        """Предобработка текста для векторизации"""
        if not text:
            return ""
        
        # Приведение к нижнему регистру
        text = text.lower()
        # Удаление лишних пробелов
        text = re.sub(r'\s+', ' ', text)
        # Удаление специальных символов
        text = re.sub(r'[^\w\s]', '', text)
        
        return text.strip()

    @staticmethod
    async def index_all_guides(db: AsyncSession) -> int:
        """Индексация всех путеводителей в векторной базе данных"""
        try:
            collection = RecommendationService.get_collection()
            
            # Получение всех путеводителей с подгрузкой тегов
            stmt = select(Guides).options(selectinload(Guides.tags))
            result = await db.execute(stmt)
            guides = result.scalars().all()
            
            if not guides:
                logger.info("There are no guides to index.")
                return 0
            
            # Подготовка данных для загрузки в ChromaDB
            documents = []
            metadatas = []
            ids = []
            
            for guide in guides:
                # Объединение заголовка, описания и тегов
                tags_text = " ".join([tag.name for tag in guide.tags]) if guide.tags else ""
                text = f"{guide.title}. {guide.description or ''} {tags_text}"
                text = RecommendationService.preprocess_text(text)
                
                if text:  # Проверка, что текст не пустой после обработки
                    documents.append(text)
                    metadatas.append({
                        "guide_id": guide.id,
                        "title": guide.title,
                        "tags": tags_text
                    })
                    ids.append(str(guide.id))
            
            # Очистка коллекции перед обновлением
            collection.delete(where={"guide_id": {"$exists": True}})
            
            # Добавление новых данных в коллекцию
            if documents:
                collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                
            return len(documents)
        except Exception as e:
            logger.error(f"Ошибка при индексации путеводителей: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error indexing guides: {str(e)}"
            )

    @staticmethod
    async def index_guide(db: AsyncSession, guide_id: int) -> bool:
        """Индексация одного путеводителя в векторной базе данных"""
        try:
            collection = RecommendationService.get_collection()
            
            # Получение путеводителя с подгрузкой тегов
            stmt = select(Guides).where(Guides.id == guide_id).options(selectinload(Guides.tags))
            result = await db.execute(stmt)
            guide = result.scalar_one_or_none()
            
            if not guide:
                logger.warning(f"Guide with id {guide_id} not found")
                return False
            
            # Подготовка данных для загрузки в ChromaDB
            tags_text = " ".join([tag.name for tag in guide.tags]) if guide.tags else ""
            text = f"{guide.title}. {guide.description or ''} {tags_text}"
            text = RecommendationService.preprocess_text(text)
            
            if not text:
                logger.warning(f"Empty content for guide with id {guide_id}")
                return False
                
            # Удаление существующего документа, если он уже был индексирован
            try:
                collection.delete(ids=[str(guide_id)])
            except:
                pass  # Игнорируем ошибку, если документ не существует
                
            # Добавление нового документа
            collection.add(
                documents=[text],
                metadatas=[{
                    "guide_id": guide.id,
                    "title": guide.title,
                    "tags": tags_text
                }],
                ids=[str(guide_id)]
            )
            
            return True
        except Exception as e:
            logger.error(f"Error indexing guides {guide_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error indexing guides: {str(e)}"
            )

    @staticmethod
    async def get_user_liked_guides(db: AsyncSession, user_id: int) -> List[Guides]:
        """Получение путеводителей, которые понравились пользователю"""
        try:
            stmt = select(Guides).join(GuideLikes).where(
                GuideLikes.user_id == user_id
            ).options(selectinload(Guides.tags))
            
            result = await db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении лайкнутых путеводителей: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error while getting liked guides"
            )

    @staticmethod
    def get_guides_by_ids(guide_ids: List[int], db: AsyncSession) -> List[Guides]:
        """Получение путеводителей по списку ID"""
        try:
            stmt = select(Guides).where(Guides.id.in_(guide_ids)).options(selectinload(Guides.tags))
            result = db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении путеводителей по ID: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error while getting guides"
            )

    @staticmethod
    async def get_recommendations_by_user_likes(
        db: AsyncSession, 
        user_id: int, 
        limit: int = 10, 
        exclude_liked: bool = True
    ) -> List[int]:
        """Получение рекомендаций на основе лайкнутых пользователем путеводителей"""
        try:
            # Получение понравившихся путеводителей
            liked_guides = await RecommendationService.get_user_liked_guides(db, user_id)
            
            if not liked_guides:
                logger.info(f"Пользователь {user_id} не лайкнул ни одного путеводителя")
                # Возвращаем популярные путеводители, если у пользователя нет лайков
                return await RecommendationService.get_popular_guides(db, limit)
            
            # Получение коллекции ChromaDB
            collection = RecommendationService.get_collection()
            
            # Создание запроса на основе лайкнутых путеводителей
            liked_ids = [guide.id for guide in liked_guides]
            liked_texts = []
            
            # Создание текста запроса из заголовков, описаний и тегов лайкнутых путеводителей
            for guide in liked_guides:
                tags_text = " ".join([tag.name for tag in guide.tags]) if guide.tags else ""
                text = f"{guide.title}. {guide.description or ''} {tags_text}"
                text = RecommendationService.preprocess_text(text)
                if text:
                    liked_texts.append(text)
            
            if not liked_texts:
                logger.warning(f"Не удалось создать запрос из лайкнутых путеводителей пользователя {user_id}")
                return await RecommendationService.get_popular_guides(db, limit)
            
            # Объединение текстов для запроса
            query_text = " ".join(liked_texts)
            
            # Исключаем уже понравившиеся путеводители из результатов
            where_clause = {}
            if exclude_liked and liked_ids:
                where_ids = [str(id) for id in liked_ids]
                where_clause = {"$and": [{"guide_id": {"$nin": liked_ids}}]}
                
            # Получение рекомендаций из ChromaDB
            results = collection.query(
                query_texts=[query_text],
                n_results=limit + len(liked_ids) if exclude_liked else limit,  # Запрашиваем больше, если исключаем лайкнутые
                where=where_clause if where_clause else None
            )
            
            # Обработка результатов
            guide_ids = []
            if 'metadatas' in results and results['metadatas']:
                for metadata in results['metadatas'][0]:
                    if 'guide_id' in metadata:
                        guide_id = metadata['guide_id']
                        if not exclude_liked or guide_id not in liked_ids:
                            guide_ids.append(guide_id)
            
            # Ограничиваем количество результатов
            return guide_ids[:limit]
            
        except Exception as e:
            logger.error(f"Ошибка при получении рекомендаций: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error while getting recommendations"
            )
    #* Обязательно потом отредачить функцию и перенести сюда логику популярных
    # @staticmethod
    # async def get_popular_guides(db: AsyncSession, limit: int = 10) -> List[int]:
    #     """Получение популярных путеводителей по количеству лайков"""
    #     try:
    #         stmt = select(Guides.id).order_by(Guides.like_count.desc()).limit(limit)
    #         result = await db.execute(stmt)
    #         return [guide_id for guide_id, in result.all()]
    #     except Exception as e:
    #         logger.error(f"Ошибка при получении популярных путеводителей: {e}")
    #         raise HTTPException(
    #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #             detail="Ошибка при получении популярных путеводителей"
    #         )
    
    # @staticmethod
    # async def get_similar_guides(db: AsyncSession, guide_id: int, limit: int = 5) -> List[int]:
    #     """Получение путеводителей, похожих на заданный"""
    #     try:
    #         # Получение исходного путеводителя
    #         stmt = select(Guides).where(Guides.id == guide_id).options(selectinload(Guides.tags))
    #         result = await db.execute(stmt)
    #         guide = result.scalar_one_or_none()
            
    #         if not guide:
    #             raise HTTPException(
    #                 status_code=status.HTTP_404_NOT_FOUND,
    #                 detail=f"Путеводитель с ID {guide_id} не найден"
    #             )
            
    #         # Получение коллекции ChromaDB
    #         collection = RecommendationService.get_collection()
            
    #         # Создание запроса из заголовка, описания и тегов путеводителя
    #         tags_text = " ".join([tag.name for tag in guide.tags]) if guide.tags else ""
    #         query_text = f"{guide.title}. {guide.description or ''} {tags_text}"
    #         query_text = RecommendationService.preprocess_text(query_text)
            
    #         if not query_text:
    #             logger.warning(f"Пустой запрос для путеводителя {guide_id}")
    #             return await RecommendationService.get_popular_guides(db, limit)
            
    #         # Получение похожих путеводителей из ChromaDB
    #         results = collection.query(
    #             query_texts=[query_text],
    #             n_results=limit + 1,  # +1 чтобы исключить сам путеводитель
    #             where={"$and": [{"guide_id": {"$ne": guide_id}}]}
    #         )
            
    #         # Обработка результатов
    #         guide_ids = []
    #         if 'metadatas' in results and results['metadatas']:
    #             for metadata in results['metadatas'][0]:
    #                 if 'guide_id' in metadata and metadata['guide_id'] != guide_id:
    #                     guide_ids.append(metadata['guide_id'])
            
    #         return guide_ids[:limit]
            
    #     except HTTPException as he:
    #         raise he
    #     except Exception as e:
    #         logger.error(f"Ошибка при получении похожих путеводителей: {e}")
    #         raise HTTPException(
    #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #             detail="Ошибка при получении похожих путеводителей"
    #         )
    
    @staticmethod
    async def get_recommendations_by_tags(db: AsyncSession, tag_ids: List[int], limit: int = 10) -> List[int]:
        """Получение рекомендаций на основе выбранных тегов"""
        try:
            # Получение имен тегов
            stmt = select(Tags).where(Tags.id.in_(tag_ids))
            result = await db.execute(stmt)
            tags = result.scalars().all()
            
            if not tags:
                logger.info("Теги не найдены")
                return await RecommendationService.get_popular_guides(db, limit)
            
            # Создание запроса из имен тегов
            tag_names = [tag.name for tag in tags]
            query_text = " ".join(tag_names)
            query_text = RecommendationService.preprocess_text(query_text)
            
            if not query_text:
                logger.warning("Пустой запрос из тегов")
                return await RecommendationService.get_popular_guides(db, limit)
            
            # Получение коллекции ChromaDB
            collection = RecommendationService.get_collection()
            
            # Получение рекомендаций из ChromaDB
            results = collection.query(
                query_texts=[query_text],
                n_results=limit
            )
            
            # Обработка результатов
            guide_ids = []
            if 'metadatas' in results and results['metadatas']:
                for metadata in results['metadatas'][0]:
                    if 'guide_id' in metadata:
                        guide_ids.append(metadata['guide_id'])
            
            return guide_ids[:limit]
            
        except Exception as e:
            logger.error(f"Ошибка при получении рекомендаций по тегам: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error getting tag recommendations"
            )
            
    @staticmethod
    async def delete_guide_from_index(guide_id: int) -> bool:
        """Удаление путеводителя из индекса"""
        try:
            collection = RecommendationService.get_collection()
            collection.delete(ids=[str(guide_id)])
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении путеводителя {guide_id} из индекса: {e}")
            return False
