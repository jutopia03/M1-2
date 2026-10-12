"""데이터 API 라우터 — 요청/응답 형태만 담당하고 로직은 data_service에 위임한다."""
import datetime as dt
from typing import Literal, Optional

from fastapi import APIRouter, Path, Query

from app.schemas.data import DataCreate, DataItem, DataUpdate, StatisticsResponse, SummaryResponse
from app.services import data_service

router = APIRouter(prefix="/api/data", tags=["data"])

DateId = Path(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="문서 ID (= 날짜, YYYY-MM-DD)",
              examples=["2026-10-11"])


# /summary, /statistics 는 /{data_id} 형태 경로보다 먼저 선언해야 ID로 해석되지 않는다.
@router.get("/summary", response_model=SummaryResponse, summary="데이터 요약 (프롬프트 주입용)")
def get_summary():
    return data_service.get_summary()


@router.get("/statistics", response_model=StatisticsResponse, summary="추가 지표 + 월별 그래프 데이터")
def get_statistics():
    return data_service.get_statistics()


@router.post("", response_model=DataItem, status_code=201, summary="새 데이터 추가")
def create_data(payload: DataCreate):
    return data_service.create_data(payload)


@router.get("", response_model=list[DataItem], summary="데이터 목록 조회")
def list_data(
    start: Optional[dt.date] = Query(None, description="시작일 (포함)"),
    end: Optional[dt.date] = Query(None, description="종료일 (포함)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="최대 개수"),
    order: Literal["asc", "desc"] = Query("asc", description="날짜 정렬"),
):
    return data_service.list_data(
        start.isoformat() if start else None,
        end.isoformat() if end else None,
        limit, order,
    )


@router.put("/{data_id}", response_model=DataItem, summary="데이터 수정 (보낸 필드만)")
def update_data(payload: DataUpdate, data_id: str = DateId):
    return data_service.update_data(data_id, payload)


@router.delete("/{data_id}", summary="데이터 삭제")
def delete_data(data_id: str = DateId):
    data_service.delete_data(data_id)
    return {"deleted": data_id}
