"""데이터(data 컬렉션) 비즈니스 로직.

- 문서 ID = 날짜(YYYY-MM-DD)
- summary/statistics는 Firestore 전체(730건+)가 필요하므로 '전체 레코드'를 메모리에 캐시한다.
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
from app.services.analysis import build_statistics, build_summary

COLLECTION = "data"
CACHE_TTL_SEC = 600

_records_cache: dict = {"value": None, "at": 0.0}


def _col():
    return get_db().collection(COLLECTION)


def _to_item(doc) -> dict:
    return {"id": doc.id, **doc.to_dict()}


def _invalidate_cache() -> None:
    _records_cache["value"] = None


def _all_records() -> list[dict]:
    cached = _records_cache["value"]
    if cached is not None and time.time() - _records_cache["at"] < CACHE_TTL_SEC:
        return cached
    records = [doc.to_dict() for doc in _col().stream()]
    _records_cache.update(value=records, at=time.time())
    return records


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
    _invalidate_cache()
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
    _invalidate_cache()
    return {"id": data_id, **merged}


def delete_data(data_id: str) -> None:
    doc_ref = _col().document(data_id)
    if not doc_ref.get().exists:
        raise NotFoundError(f"{data_id} 데이터가 없습니다.")
    doc_ref.delete()
    _invalidate_cache()


def get_summary() -> dict:
    return build_summary(_all_records())


def get_statistics() -> dict:
    return build_statistics(_all_records())
