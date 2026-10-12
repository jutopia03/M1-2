"""대화 기록(conversations 컬렉션) 비즈니스 로직.

문서 구조: {title, created_at, updated_at, message_count, messages: [{role, content, created_at}]}
- 문서 ID는 Firestore 자동 ID
- messages는 문서 안의 배열 (대화 하나 = 문서 하나 -> 불러오기 1회 읽기)
"""
import datetime as dt
from typing import Optional

from app.core.errors import NotFoundError
from app.core.firebase import get_db

COLLECTION = "conversations"
TITLE_LEN = 30
LIST_FIELDS = ["title", "created_at", "updated_at", "message_count"]


def _col():
    return get_db().collection(COLLECTION)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def make_title(messages: list[dict]) -> str:
    first = next((m["content"] for m in messages if m["role"] == "user"), "")
    first = " ".join(first.split())
    if not first:
        return "새 대화"
    return first if len(first) <= TITLE_LEN else first[:TITLE_LEN] + "…"


def create_conversation(messages: list[dict], title: Optional[str] = None) -> dict:
    now = _now()
    messages = [{**m, "created_at": m.get("created_at") or now} for m in messages]
    doc = {
        "title": title or make_title(messages),
        "created_at": now,
        "updated_at": now,
        "message_count": len(messages),
        "messages": messages,
    }
    ref = _col().document()  # 자동 ID
    ref.set(doc)
    return {"id": ref.id, **doc}


def list_conversations(limit: int = 50) -> list[dict]:
    from google.cloud.firestore import Query

    query = (_col().select(LIST_FIELDS)  # messages 필드는 읽지 않는다
             .order_by("updated_at", direction=Query.DESCENDING)
             .limit(limit))
    return [{"id": d.id, **d.to_dict()} for d in query.stream()]


def get_conversation(conversation_id: str) -> dict:
    snap = _col().document(conversation_id).get()
    if not snap.exists:
        raise NotFoundError(f"대화 {conversation_id} 를 찾을 수 없습니다.")
    return {"id": snap.id, **snap.to_dict()}


def append_messages(conversation_id: str, new_messages: list[dict]) -> None:
    ref = _col().document(conversation_id)
    snap = ref.get()
    if not snap.exists:
        raise NotFoundError(f"대화 {conversation_id} 를 찾을 수 없습니다.")
    messages = snap.to_dict().get("messages", []) + new_messages
    ref.update({"messages": messages, "message_count": len(messages), "updated_at": _now()})


def delete_conversation(conversation_id: str) -> None:
    ref = _col().document(conversation_id)
    if not ref.get().exists:
        raise NotFoundError(f"대화 {conversation_id} 를 찾을 수 없습니다.")
    ref.delete()
