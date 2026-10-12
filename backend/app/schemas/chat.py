"""AI 채팅 API 모델"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    # Swagger 기본 예시: 새 대화 시작 (conversation_id 생략).
    # 지정하지 않으면 Swagger가 정규식에 맞는 무작위 ID를 만들어 넣어 404가 난다.
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [
            {"message": "가장 더웠던 날은 언제야?"},
            {"message": "그날 최저기온은?", "conversation_id": "<이전 응답의 conversation_id>"},
        ]},
    )

    message: str = Field(..., min_length=1, max_length=1000, description="사용자 질문",
                         examples=["가장 더웠던 날은 언제야?"])
    conversation_id: Optional[str] = Field(
        None, max_length=100, pattern=r"^[A-Za-z0-9_-]+$",
        description="이어서 대화할 ID. 생략하면 새 대화를 만든다.")

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("질문이 비어 있습니다.")
        return v


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
