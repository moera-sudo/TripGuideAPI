import time
import uuid
from typing import Callable
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


logger = logging.getLogger("http_middleware")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, 
        app: ASGIApp, 
        exclude_paths: list[str] = None,
        log_request_body: bool = False
    ):
        """        
        Args:
            app: ASGI приложение
            exclude_paths: Список путей, которые не нужно логировать (например ['/health', '/metrics'])
            log_request_body: Логировать ли тело запроса (может содержать конфиденциальные данные)
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or []
        self.log_request_body = log_request_body
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Проверяем, нужно ли логировать данный путь
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Генерируем уникальный ID запроса для отслеживания
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Начальная информация о запросе
        start_time = time.time()
        
        # Логирование информации о запросе
        client_host = request.client.host if request.client else "unknown"
        logger.info(
            f"Request started | {request_id} | {request.method} {request.url.path} | "
            f"Client: {client_host} | User-Agent: {request.headers.get('user-agent', 'unknown')}"
        )
        
        # Логирование тела запроса, если включено
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Копируем тело, потому что оно может быть прочитано только один раз
                body = await request.body()
                # Преобразуем байты в строку и ограничиваем длину для лога
                body_str = body.decode('utf-8')[:1000]
                if len(body) > 1000:
                    body_str += "... [truncated]"
                
                logger.debug(f"Request body | {request_id} | {body_str}")
                
                # Необходимо восстановить тело запроса для дальнейшей обработки
                async def receive():
                    return {"type": "http.request", "body": body}
                
                request._receive = receive
            except Exception as e:
                logger.warning(f"Failed to log request body | {request_id} | {str(e)}")
                
        # Обработка запроса и перехват ответа
        try:
            response = await call_next(request)
            
            # Вычисляем время обработки
            process_time = time.time() - start_time
            
            # Логирование информации о завершенном запросе
            logger.info(
                f"Request finished | {request_id} | {request.method} {request.url.path} | "
                f"Status: {response.status_code} | Time: {process_time:.4f}s"
            )
            
            # Добавляем ID запроса в заголовки ответа для отслеживания
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Логирование неперехваченных исключений
            process_time = time.time() - start_time
            logger.error(
                f"Request failed | {request_id} | {request.method} {request.url.path} | "
                f"Error: {str(e)} | Time: {process_time:.4f}s", 
                exc_info=True
            )
            raise  # Повторно возбуждаем исключение для обработки в FastAPI