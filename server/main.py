from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server import settings
from server.api import api_router
from server.middleware import RequestLoggingMiddleware
from server.logging_config import configure_logging

# Configure shared Loguru logging
configure_logging()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.UVICORN_HOST, port=settings.UVICORN_PORT)
