"""데이터 API 요청/응답 모델 (Pydantic).
요청 단계에서 형식·범위를 검증해, 잘못된 값이 Firestore에 들어가기 전에 422로 막는다."""
import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

KST = dt.timezone(dt.timedelta(hours=9))
TEMP_RANGE = {"ge": -50, "le": 50}  # 대전 기온으로 불가능한 값 차단


def validate_temps(value: Optional[float], tmin: Optional[float], tmax: Optional[float]) -> None:
    """최저 <= 평균 <= 최고 관계 검사 (값이 있는 것끼리만)."""
    if tmin is not None and tmax is not None and tmin > tmax:
        raise ValueError("최저기온(min)이 최고기온(max)보다 클 수 없습니다.")
    if value is not None and tmin is not None and value < tmin:
        raise ValueError("평균기온(value)이 최저기온(min)보다 낮을 수 없습니다.")
    if value is not None and tmax is not None and value > tmax:
        raise ValueError("평균기온(value)이 최고기온(max)보다 높을 수 없습니다.")


class DataCreate(BaseModel):
    """POST /api/data 요청. date가 문서 ID가 된다."""
    model_config = ConfigDict(extra="forbid")

    date: dt.date = Field(..., description="관측 날짜 (YYYY-MM-DD). 문서 ID로 사용", examples=["2026-10-12"])
    value: float = Field(..., **TEMP_RANGE, description="일평균기온 (°C)", examples=[18.4])
    memo: str = Field("", max_length=200, description="메모", examples=["산책하기 좋은 날"])
    min: Optional[float] = Field(None, **TEMP_RANGE, description="최저기온 (°C)", examples=[12.1])
    max: Optional[float] = Field(None, **TEMP_RANGE, description="최고기온 (°C)", examples=[24.0])
    rain: Optional[float] = Field(None, ge=0, le=1000, description="일강수량 (mm)", examples=[0.0])

    @field_validator("date")
    @classmethod
    def not_future(cls, v: dt.date) -> dt.date:
        if v > dt.datetime.now(KST).date():
            raise ValueError("미래 날짜의 관측값은 추가할 수 없습니다.")
        return v

    @model_validator(mode="after")
    def check_temps(self):
        validate_temps(self.value, self.min, self.max)
        return self


class DataUpdate(BaseModel):
    """PUT /api/data/{id} 요청. 보낸 필드만 수정한다.
    날짜는 문서 ID(데이터의 정체성)이므로 수정 불가 -> date를 보내면 422."""
    model_config = ConfigDict(extra="forbid")

    value: Optional[float] = Field(None, **TEMP_RANGE, examples=[19.0])
    memo: Optional[str] = Field(None, max_length=200, examples=["메모 수정"])
    min: Optional[float] = Field(None, **TEMP_RANGE)
    max: Optional[float] = Field(None, **TEMP_RANGE)
    rain: Optional[float] = Field(None, ge=0, le=1000)

    @model_validator(mode="after")
    def check(self):
        if not self.model_fields_set:
            raise ValueError("수정할 필드를 하나 이상 보내야 합니다.")
        validate_temps(self.value, self.min, self.max)
        return self


class DataItem(BaseModel):
    """데이터 1건 응답"""
    id: str = Field(..., description="문서 ID (= 날짜)")
    date: str
    value: float
    memo: str = ""
    min: Optional[float] = None
    max: Optional[float] = None
    rain: Optional[float] = None


class Extreme(BaseModel):
    value: float
    date: str


class Metrics(BaseModel):
    """일평균기온(value) 기준 통계"""
    average: Optional[float] = None
    max: Optional[Extreme] = Field(None, description="일평균기온이 가장 높았던 날")
    min: Optional[Extreme] = Field(None, description="일평균기온이 가장 낮았던 날")


class Extremes(BaseModel):
    """최고/최저기온·강수량 기준 극값"""
    highest_max_temp: Optional[Extreme] = Field(None, description="하루 최고기온 중 가장 높았던 날")
    lowest_min_temp: Optional[Extreme] = Field(None, description="하루 최저기온 중 가장 낮았던 날")
    max_rain: Optional[Extreme] = Field(None, description="일강수량이 가장 많았던 날 (mm)")


class MonthlyStat(BaseModel):
    avg: float
    days: int = Field(..., description="해당 월에 포함된 일수 (일부 월은 30일 미만)")


class RecentDay(BaseModel):
    date: str
    value: float
    min: Optional[float] = None
    max: Optional[float] = None
    rain: Optional[float] = None
    memo: str = ""


class SummaryResponse(BaseModel):
    """GET /api/data/summary 응답 — 시스템 프롬프트에 그대로 주입된다."""
    period: Optional[str]
    count: int
    unit: str
    metrics: Metrics
    extremes: Extremes = Extremes()
    trend: str
    monthly_avg: dict[str, MonthlyStat]
    recent_days: list[RecentDay]
