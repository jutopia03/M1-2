"""대화 기록 API 모델.
목록 조회(GET /api/conversations)는 messages를 빼고 가볍게, 상세 조회(GET /api/conversations/{id})에서만 전체 messages를 준다."""
import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)
    created_at: Optional[dt.datetime] = None


class ConversationCreate(BaseModel):
    """POST /api/conversations — 빈 대화 생성 또는 메시지 목록 직접 저장.
    (일반적인 저장은 /api/chat 이 자동으로 한다)"""
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(None, max_length=100, description="생략 시 첫 질문으로 자동 생성")
    messages: list[Message] = Field(default_factory=list, max_length=200)


class ConversationSummary(BaseModel):
    """대화 목록의 한 항목 (messages 제외)"""
    id: str
    title: str
    created_at: dt.datetime
    updated_at: dt.datetime
    message_count: int


class ConversationDetail(ConversationSummary):
    messages: list[Message]
