from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import logging
import uvicorn


from models.basemodel import BaseModel
from config.appsettings import Settings
from config.database import engine
from middlewares.LoggerMiddleware import RequestLoggingMiddleware
from routes.auth import router as AuthRouter


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # await conn.run_sync(BaseModel.metadata.drop_all)
        await conn.run_sync(BaseModel.metadata.create_all)

    yield

    await engine.dispose()

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

uploads_dir = Path('uploads')
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory='uploads'), name='uploads')

#* Команда для запуска uvicorn main:app --reload