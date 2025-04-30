from contextlib import asynccontextmanager
import time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import logging
import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession


from models.basemodel import BaseModel
from config.appsettings import Settings
from config.database import engine
from config.config import uploads_dir, content_dir
from middlewares.LoggerMiddleware import RequestLoggingMiddleware
from routes.auth import router as AuthRouter
from routes.user import router as UserRouter
from routes.guides import router as GuideRouter
from routes.pages import router as PageRouter
from services.RecommendationService import RecommendationService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создание таблиц в БД
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
        await conn.run_sync(BaseModel.metadata.create_all)
        
    
    # Инициализация сервиса рекомендаций
    recommendation_service = RecommendationService()
    
    # Проверка и индексация путеводителей
    db = AsyncSession(engine)
    try:
        start_time = time.time()
        indexed_count = await recommendation_service.index_all_guides(db)
        elapsed = time.time() - start_time
        
        logging.info(f"Initial indexing completed. Indexed {indexed_count} guides in {elapsed:.2f} seconds")
        
    except Exception as e:
        logging.critical(f"Failed to index guides on startup: {e}")
        # Можно добавить отправку уведомления администратору
        raise  # Прерываем запуск если индексация критически важна
    finally:
        await db.close()
    
    yield  # Приложение работает
    
    # Завершение работы
    await engine.dispose()
    logging.info("Application shutdown completed")


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Логи в консоль
        #TODO logging.FileHandler("app.log")  # Логи в файл
    ]
)
        

app = FastAPI(
    title=Settings.APP_VERSION,
    version=Settings.APP_VERSION,
    description=Settings.APP_DESCRIPTION,
    docs_url="/api/docs" if Settings.DEBUG else None,
    redoc_url="/api/redoc" if Settings.DEBUG else None,
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.add_middleware(
    RequestLoggingMiddleware,
    exclude_paths=["/docs", "/redoc"],  # Пути, которые не нужно логировать
    log_request_body=False
)

app.include_router(AuthRouter)
app.include_router(UserRouter)
app.include_router(GuideRouter)
app.include_router(PageRouter)

app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

app.mount("/content", StaticFiles(directory=content_dir), name="content")

#* Команда для запуска uvicorn main:app --reload