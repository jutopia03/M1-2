"""AI 채팅 API 라우터"""
from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse,
             summary="AI 채팅 (데이터 요약 주입 + 대화 자동 저장)")
def chat(payload: ChatRequest):
    return chat_service.chat(payload.message, payload.conversation_id)
