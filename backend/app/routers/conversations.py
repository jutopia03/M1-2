"""대화 기록 API 라우터"""
from fastapi import APIRouter, Path, Query

from app.schemas.conversation import ConversationCreate, ConversationDetail, ConversationSummary
from app.services import conversation_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

ConvId = Path(..., pattern=r"^[A-Za-z0-9_-]{1,100}$", description="대화 ID")


@router.post("", response_model=ConversationDetail, status_code=201, summary="대화 저장")
def create_conversation(payload: ConversationCreate):
    messages = [m.model_dump() for m in payload.messages]
    return conversation_service.create_conversation(messages, payload.title)


@router.get("", response_model=list[ConversationSummary],
            summary="대화 목록 조회 (최근 수정순, messages 미포함)")
def list_conversations(limit: int = Query(50, ge=1, le=200)):
    return conversation_service.list_conversations(limit)


@router.get("/{conversation_id}", response_model=ConversationDetail, summary="특정 대화 불러오기 (전체 messages)")
def get_conversation(conversation_id: str = ConvId):
    return conversation_service.get_conversation(conversation_id)


@router.delete("/{conversation_id}", summary="대화 삭제")
def delete_conversation(conversation_id: str = ConvId):
    conversation_service.delete_conversation(conversation_id)
    return {"deleted": conversation_id}
