"""
시계열 분석 / 요약 생성 (표준 라이브러리만 사용)

data/analyze.py(로컬 분석)와 백엔드가 같은 함수를 공유한다.
레코드 형태: {date, value, memo, min?, max?, rain?}
"""
from collections import defaultdict
from statistics import mean

UNIT = "°C (일평균기온)"


def _trend(values: list[float], window: int = 7, threshold: float = 0.5) -> str:
    """최근 window일 평균과 직전 window일 평균을 비교한다.
    기온은 계절성이 강해 전체 기간의 상승/하강은 의미가 없으므로 '최근' 변화만 본다."""
    if len(values) < window * 2:
        return "판단 불가 (데이터 부족)"
    recent = mean(values[-window:])
    prev = mean(values[-window * 2:-window])
    diff = recent - prev
    if abs(diff) < threshold:
        label = "유지"
    else:
        label = "상승" if diff > 0 else "하강"
    return f"{label} (최근 {window}일 평균 {recent:.1f}°C, 직전 {window}일 대비 {diff:+.1f}°C)"


def build_summary(records: list[dict], recent_n: int = 14) -> dict:
    """프롬프트 주입용 요약.
    - max/min에 날짜를 붙여 '가장 더웠던 날은?'에 답할 수 있게 한다.
      metrics는 일평균기온 기준, extremes는 최고/최저기온·강수량 기준 (혼동 방지를 위해 분리)
    - 월별 평균(+일수)으로 '작년 이맘때보다?' 같은 계절 비교를 가능하게 한다.
    - 최근 N일 원본으로 '어제 몇 도?' 같은 질문에 답할 수 있게 한다."""
    if not records:
        return {"period": None, "count": 0, "unit": UNIT, "metrics": {}, "extremes": {},
                "trend": "데이터 없음", "monthly_avg": {}, "recent_days": []}

    rows = sorted(records, key=lambda r: r["date"])
    values = [r["value"] for r in rows]
    hottest = max(rows, key=lambda r: r["value"])
    coldest = min(rows, key=lambda r: r["value"])

    # 일평균기온과 별개로, 최고/최저기온·강수량 기준 극값 (해당 필드가 있는 레코드만)
    def _extreme(field: str, pick):
        cands = [r for r in rows if r.get(field) is not None]
        if not cands:
            return None
        r = pick(cands, key=lambda x: x[field])
        return {"value": r[field], "date": r["date"]}

    extremes = {
        "highest_max_temp": _extreme("max", max),   # 하루 최고기온 중 가장 높았던 날
        "lowest_min_temp": _extreme("min", min),    # 하루 최저기온 중 가장 낮았던 날
        "max_rain": _extreme("rain", max),          # 일강수량 최다
    }

    by_month = defaultdict(list)
    for r in rows:
        by_month[r["date"][:7]].append(r["value"])
    monthly = {m: {"avg": round(mean(v), 1), "days": len(v)} for m, v in by_month.items()}

    return {
        "period": f"{rows[0]['date']} ~ {rows[-1]['date']}",
        "count": len(rows),
        "unit": UNIT,
        "metrics": {
            "average": round(mean(values), 1),
            "max": {"value": hottest["value"], "date": hottest["date"]},
            "min": {"value": coldest["value"], "date": coldest["date"]},
        },
        "extremes": extremes,
        "trend": _trend(values),
        "monthly_avg": monthly,
        "recent_days": [
            {k: r.get(k) for k in ("date", "value", "min", "max", "rain", "memo")}
            for r in rows[-recent_n:]
        ],
    }
