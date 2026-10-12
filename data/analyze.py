"""
대전 일평균기온 분석 스크립트 (로컬)

흐름: 기상청 ASOS CSV(CP949) -> 레코드 리스트 -> summary(dict)
요약 로직(build_summary)은 백엔드의 backend/app/services/analysis.py 를 그대로 사용한다.
-> 로컬 분석 결과와 서비스의 /api/data/summary 결과가 항상 같은 기준으로 계산된다.

레코드 형태(B안): {date, value, memo, min?, max?, rain?}
  value = 일평균기온(°C), min/max = 최저/최고기온, rain = 일강수량(mm)

실행: python analyze.py [CSV 경로]
"""
import csv
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent
sys.path.insert(0, str(DATA_DIR.parent / "backend"))
from app.services.analysis import build_summary  # noqa: E402


def _to_float(text: str):
    text = (text or "").strip()
    return float(text) if text else None


def find_csv() -> Path:
    files = sorted(DATA_DIR.glob("OBS_ASOS_DD_*.csv"))
    if not files:
        sys.exit("data/ 폴더에 OBS_ASOS_DD_*.csv 파일이 없습니다.")
    return files[-1]


def load_csv(path: Path) -> list[dict]:
    """기상청 CSV를 레코드 리스트로 변환한다. 컬럼은 이름 앞부분으로 찾는다."""
    with open(path, encoding="cp949", newline="") as f:
        reader = csv.DictReader(f)

        def col(prefix: str) -> str:
            for name in reader.fieldnames:
                if name.startswith(prefix):
                    return name
            raise KeyError(f"'{prefix}' 컬럼을 찾을 수 없습니다: {reader.fieldnames}")

        c_date, c_avg = col("일시"), col("평균기온")
        c_min, c_max, c_rain = col("최저기온"), col("최고기온"), col("일강수량")

        records = []
        for row in reader:
            value = _to_float(row[c_avg])
            if value is None:  # 평균기온이 없는 날은 제외
                continue
            records.append({
                "date": row[c_date].strip(),
                "value": value,
                "min": _to_float(row[c_min]),
                "max": _to_float(row[c_max]),
                # 기상청 CSV는 비가 오지 않은 날을 빈칸으로 둔다 -> 0.0
                "rain": _to_float(row[c_rain]) or 0.0,
                "memo": "",
            })
    return records


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else find_csv()
    records = load_csv(path)
    summary = build_summary(records)

    out = DATA_DIR / "summary_sample.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    compact = json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
    print(f"원본: {path.name} / 레코드 {len(records)}개")
    print(f"저장: {out.name} / 프롬프트 주입 시 약 {len(compact):,}자")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("monthly_avg", "recent_days")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
