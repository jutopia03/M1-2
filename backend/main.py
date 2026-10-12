"""FastAPI 진입점. 실행: uvicorn main:app --reload  (backend 폴더에서)"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import (ConflictError, InvalidDataError, NotFoundError,
                             ServiceUnavailableError, UpstreamError)
from app.routers import chat, conversations, data

app = FastAPI(
    title="M1-2 대전 날씨 AI 비서 API",
    description="대전 일평균기온 데이터(기상청 ASOS) 기반 AI 챗봇 백엔드",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 도메인 예외 -> HTTP 상태 코드
def _handler(status: int):
    async def handle(_: Request, exc: Exception):
        return JSONResponse(status_code=status, content={"detail": str(exc)})
    return handle


app.add_exception_handler(NotFoundError, _handler(404))
app.add_exception_handler(ConflictError, _handler(409))
app.add_exception_handler(InvalidDataError, _handler(422))
app.add_exception_handler(UpstreamError, _handler(502))
app.add_exception_handler(ServiceUnavailableError, _handler(503))


@app.get("/", tags=["health"], summary="서버 상태 확인 (콜드스타트 깨우기용)")
def health():
    return {"status": "ok"}


app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)
