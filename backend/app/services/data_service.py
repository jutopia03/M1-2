"""데이터(data 컬렉션) 비즈니스 로직.

- 문서 ID = 날짜(YYYY-MM-DD)
- summary는 매번 Firestore 전체(730건+)를 읽으므로 메모리에 캐시한다.
  무료 티어 읽기 한도(일 5만 건)를 아끼고 /api/chat 응답 속도를 높이기 위함.
  이 서버를 통한 추가/수정/삭제 시 캐시를 비우고, 콘솔 직접 수정 대비 TTL도 둔다.
"""
import time
from typing import Optional

from google.api_core.exceptions import Conflict
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore import Query

from app.core.errors import ConflictError, InvalidDataError, NotFoundError
from app.core.firebase import get_db
from app.schemas.data import DataCreate, DataUpdate, validate_temps
from app.services.analysis import build_summary

COLLECTION = "data"
SUMMARY_TTL_SEC = 600

_summary_cache: dict = {"value": None, "at": 0.0}


def _col():
    return get_db().collection(COLLECTION)


def _to_item(doc) -> dict:
    return {"id": doc.id, **doc.to_dict()}


def _invalidate_summary() -> None:
    _summary_cache["value"] = None


def list_data(start: Optional[str] = None, end: Optional[str] = None,
              limit: Optional[int] = None, order: str = "asc") -> list[dict]:
    query = _col()
    if start:
        query = query.where(filter=FieldFilter("date", ">=", start))
    if end:
        query = query.where(filter=FieldFilter("date", "<=", end))
    direction = Query.DESCENDING if order == "desc" else Query.ASCENDING
    query = query.order_by("date", direction=direction)
    if limit:
        query = query.limit(limit)
    return [_to_item(doc) for doc in query.stream()]


def create_data(payload: DataCreate) -> dict:
    record = payload.model_dump()
    record["date"] = payload.date.isoformat()
    doc_ref = _col().document(record["date"])
    try:
        doc_ref.create(record)  # 이미 있으면 실패 -> 중복 방지 (원자적)
    except Conflict:
        raise ConflictError(f"{record['date']} 데이터가 이미 있습니다. 수정(PUT)을 사용하세요.")
    _invalidate_summary()
    return {"id": doc_ref.id, **record}


def update_data(data_id: str, payload: DataUpdate) -> dict:
    doc_ref = _col().document(data_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise NotFoundError(f"{data_id} 데이터가 없습니다.")

    changes = payload.model_dump(exclude_unset=True)
    merged = {**snap.to_dict(), **changes}
    try:
        validate_temps(merged.get("value"), merged.get("min"), merged.get("max"))
    except ValueError as e:
        raise InvalidDataError(str(e))

    doc_ref.update(changes)
    _invalidate_summary()
    return {"id": data_id, **merged}


def delete_data(data_id: str) -> None:
    doc_ref = _col().document(data_id)
    if not doc_ref.get().exists:
        raise NotFoundError(f"{data_id} 데이터가 없습니다.")
    doc_ref.delete()
    _invalidate_summary()


def get_summary() -> dict:
    cached = _summary_cache["value"]
    if cached is not None and time.time() - _summary_cache["at"] < SUMMARY_TTL_SEC:
        return cached
    records = [doc.to_dict() for doc in _col().stream()]
    summary = build_summary(records)
    _summary_cache.update(value=summary, at=time.time())
    return summary
