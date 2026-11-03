"""NeuroFence application factory. Run with: uvicorn app.main:create_app --factory"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import health
from app.config import APP_VERSION, Settings, get_settings
from app.db.models import Base
from app.db.session import create_db_engine
from app.schemas import ProblemDetail, ProblemFieldError

API_PREFIX = "/api/v1"
PROBLEM_JSON = "application/problem+json"
logger = logging.getLogger("neurofence")


def problem_response(
    status: int,
    detail: str | None = None,
    errors: list[ProblemFieldError] | None = None,
    instance: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    try:
        title = HTTPStatus(status).phrase
    except ValueError:
        title = "Error"
    body = ProblemDetail(title=title, status=status, detail=detail, instance=instance, errors=errors)
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json", exclude_none=True),
        media_type=PROBLEM_JSON,
        headers=headers,
    )


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else None
    return problem_response(
        exc.status_code, detail=detail, instance=request.url.path, headers=exc.headers
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        ProblemFieldError(
            field=".".join(str(part) for part in err.get("loc", ())),
            message=str(err.get("msg", "invalid value")),  # never the submitted value
        )
        for err in exc.errors()
    ]
    return problem_response(
        422, detail="Request validation failed", errors=errors, instance=request.url.path
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s", request.url.path)  # stack trace stays in server log
    return problem_response(500, detail="Internal server error", instance=request.url.path)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)  # Alembic migrations are added in a later stage

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        engine.dispose()

    is_prod = settings.env == "production"
    app = FastAPI(
        title="NeuroFence API",
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if is_prod else "/openapi.json",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith(API_PREFIX):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health.router, prefix=API_PREFIX)
    return app