import time
from typing import Awaitable, Callable, Optional

from loguru import logger as loguru_logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Lightweight request logging middleware that can be reused across services."""

    def __init__(self, app, logger: Optional[object] = None):
        super().__init__(app)
        # Loguru logger or compatible interface with .info/.exception
        self.logger = (logger or loguru_logger).bind(component="http")

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.exception(
                "{method} {path} -> unhandled error ({duration:.2f} ms) [client={client}]",
                method=request.method,
                path=request.url.path,
                duration=duration_ms,
                client=request.client.host if request.client else "unknown",
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        self.logger.info(
            "{method} {path} -> {status} ({duration:.2f} ms) [client={client}]",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration=duration_ms,
            client=request.client.host if request.client else "unknown",
        )
        return response
