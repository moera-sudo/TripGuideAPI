import time
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
from collections import Counter, defaultdict
import re
from chromadb.config import Settings
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class RecommendationService:
    """Сервис рекомендаций с улучшенной производительностью и точностью"""
    
    # Конфигурация
    MODEL_NAME = "all-MiniLM-L6-v2"
    COLLECTION_NAME = "travel_guides"
    EMBEDDING_CACHE_SIZE = 1000
    MAX_CONCURRENT_EMBEDDINGS = 4
    
    # Веса для разных частей контента
    TITLE_WEIGHT = 5
    DESCRIPTION_WEIGHT = 3
    TAGS_WEIGHT = 2

    def __init__(self):
        try:
            # Инициализация модели для эмбеддингов
            self.embedding_model = SentenceTransformer(self.MODEL_NAME)
            
            # Новый клиент ChromaDB
            self.chroma_client = chromadb.PersistentClient(
                path="./chroma_db",
                settings=Settings(allow_reset=True)
            )
            
            # Коллекция
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self.MODEL_NAME
                )
            )
            
        except Exception as e:
            logger.critical(f"Ошибка инициализации: {e}")
            raise RuntimeError("Не удалось инициализировать сервис рекомендаций")
    
    @staticmethod
    def preprocess_text(text: str) -> str:
        """Предварительная обработка текста"""
        if not text:
            return ""
        return text.lower().strip()
    
    async def index_all_guides(self, db: AsyncSession) -> int:
        """Полная индексация всех путеводителей"""
        try:
            start_time = time.time()
            
            # Очистка существующей коллекции
            try:
                self.chroma_client.delete_collection(name=self.COLLECTION_NAME)
            except:
                pass
                
            # Создание новой коллекции
            self.collection = self.chroma_client.create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self.MODEL_NAME
                )
            )
            
            # Пакетная индексация
            batch_size = 100
            offset = 0
            total_indexed = 0
            
            while True:
                stmt = select(Guides).options(selectinload(Guides.tags)).offset(offset).limit(batch_size)
                result = await db.execute(stmt)
                guides = result.scalars().all()
                
                if not guides:
                    break
                
                # Подготовка данных для индексации
                documents = []
                metadatas = []
                ids = []
                
                for guide in guides:
                    doc = self._create_guide_document(guide)
                    if doc:
                        documents.append(doc)
                        metadatas.append({
                            "guide_id": guide.id,
                            "title": guide.title,
                            "tags": " ".join([tag.name for tag in guide.tags]) if guide.tags else ""
                        })
                        ids.append(str(guide.id))
                
                # Добавление в коллекцию
                if documents:
                    self.collection.add(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )
                    total_indexed += len(documents)
                
                offset += batch_size
            
            logger.info(f"Индексация завершена. Путеводителей: {total_indexed}, время: {time.time()-start_time:.2f}с")
            return total_indexed
            
        except Exception as e:
            logger.error(f"Ошибка полной индексации: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка индексации путеводителей: {e}"
            )
    
    async def index_guide(self, guide: Guides) -> bool:
        """Индексация одного путеводителя"""
        try:
            doc = self._create_guide_document(guide)
            if not doc:
                return False
                
            self.collection.upsert(
                ids=[str(guide.id)],
                documents=[doc],
                metadatas=[{
                    "guide_id": guide.id,
                    "title": guide.title,
                    "tags": " ".join([tag.name for tag in guide.tags]) if guide.tags else ""
                }]
            )
            return True
            
        except Exception as e:
            logger.error(f"Ошибка индексации путеводителя {guide.id}: {e}")
            return False
    
    def _create_guide_document(self, guide: Guides) -> str:
        """Создание документа для индексации с учетом весов"""
        parts = []
        
        if guide.title:
            parts.extend([self.preprocess_text(guide.title)] * 5)  # title_weight=0.5 → 5 повторов
            
        if guide.description:
            parts.extend([self.preprocess_text(guide.description)] * 3)  # description_weight=0.3 → 3 повтора
            
        if guide.tags:
            tags_text = " ".join(self.preprocess_text(tag.name) for tag in guide.tags)
            parts.extend([tags_text] * 2)  # tags_weight=0.2 → 2 повтора
        
        return " ".join(parts)
    
    async def get_user_recommendations(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int = 10,
        exclude_liked: bool = True
    ) -> List[int]:
        """Получение рекомендаций для пользователя"""
        try:
            # Контентные рекомендации
            content_recs = await self._get_content_recommendations(db, user_id, limit, exclude_liked)
            
            # Если недостаточно, добавляем рекомендации по тегам
            if len(content_recs) < limit:
                tag_recs = await self._get_tag_recommendations(db, user_id, limit - len(content_recs), exclude_liked)
                content_recs.extend(tag_recs)
            
            # Если все еще недостаточно, добавляем популярные
            if len(content_recs) < limit:
                popular_recs = await self._get_popular_guides(db, limit - len(content_recs))
                content_recs.extend(popular_recs)
            
            return content_recs[:limit]
            
        except Exception as e:
            logger.error(f"Ошибка рекомендаций для пользователя {user_id}: {e}")
            return await self._get_popular_guides(db, limit)
    
    async def _get_content_recommendations(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int,
        exclude_liked: bool
    ) -> List[int]:
        """Рекомендации на основе контента"""
        liked_guides = await self._get_liked_guides(db, user_id)
        if not liked_guides:
            return []
            
        # Создаем запрос из лайкнутых путеводителей
        query_parts = [self._create_guide_document(g) for g in liked_guides]
        query_text = " ".join([p for p in query_parts if p])
        
        if not query_text:
            return []
            
        # Исключаем лайкнутые
        liked_ids = [g.id for g in liked_guides] if exclude_liked else []
        where = {"guide_id": {"$nin": liked_ids}} if liked_ids else None
        
        # Запрос к ChromaDB
        results = self.collection.query(
            query_texts=[query_text],
            n_results=limit + len(liked_ids),
            where=where
        )
        
        return [m["guide_id"] for m in results["metadatas"][0] if m and "guide_id" in m][:limit]
    
    async def _get_tag_recommendations(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int,
        exclude_liked: bool
    ) -> List[int]:
        """Рекомендации на основе тегов"""
        liked_guides = await self._get_liked_guides(db, user_id)
        if not liked_guides:
            return []
            
        # Собираем популярные теги
        tag_counts = {}
        for guide in liked_guides:
            for tag in guide.tags:
                tag_counts[tag.id] = tag_counts.get(tag.id, 0) + 1
        
        if not tag_counts:
            return []
            
        # Ищем путеводители с этими тегами
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        tag_ids = [tag_id for tag_id, _ in top_tags]
        
        stmt = (
            select(Guides.id)
            .join(GuideTags)
            .where(GuideTags.tag_id.in_(tag_ids))
            .group_by(Guides.id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        
        if exclude_liked:
            liked_ids = [g.id for g in liked_guides]
            stmt = stmt.where(Guides.id.notin_(liked_ids))
            
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]
    
    async def _get_liked_guides(self, db: AsyncSession, user_id: int) -> List[Guides]:
        """Получение лайкнутых путеводителей"""
        stmt = (
            select(Guides)
            .join(GuideLikes)
            .where(GuideLikes.user_id == user_id)
            .options(selectinload(Guides.tags))
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def _get_popular_guides(self, db: AsyncSession, limit: int) -> List[int]:
        """Получение популярных путеводителей"""
        stmt = select(Guides.id).order_by(Guides.like_count.desc()).limit(limit)
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]
    
    async def delete_guide(self, guide_id: int) -> bool:
        """Удаление путеводителя из индекса"""
        try:
            self.collection.delete(ids=[str(guide_id)])
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления путеводителя {guide_id}: {e}")
            return False