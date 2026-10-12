"""
Firestore 업로드용 시드 데이터 생성 스크립트

CSV -> seed.json (Firestore 'data' 컬렉션에 넣을 문서 리스트)
실제 업로드는 Firebase 서비스 계정 키가 준비된 뒤 별도 스크립트로 진행한다.

memo 자동 생성 규칙 (특이 기상만 표시, 나머지는 빈 문자열):
  - 일강수량 30mm 이상  -> "호우 (강수 N mm)"
  - 최고기온 33°C 이상  -> "폭염 (최고 N°C)"
  - 최저기온 -10°C 이하 -> "한파 (최저 N°C)"
  - 일교차 15°C 이상    -> "큰 일교차 (N°C)"

실행: python prepare_seed.py
"""
import json
from collections import Counter

from analyze import DATA_DIR, find_csv, load_csv


def make_memo(r: dict) -> str:
    notes = []
    if r["rain"] >= 30:
        notes.append(f"호우 (강수 {r['rain']}mm)")
    if r["max"] is not None and r["max"] >= 33:
        notes.append(f"폭염 (최고 {r['max']}°C)")
    if r["min"] is not None and r["min"] <= -10:
        notes.append(f"한파 (최저 {r['min']}°C)")
    if r["max"] is not None and r["min"] is not None and r["max"] - r["min"] >= 15:
        notes.append(f"큰 일교차 ({r['max'] - r['min']:.1f}°C)")
    return ", ".join(notes)


def main():
    records = load_csv(find_csv())
    for r in records:
        r["memo"] = make_memo(r)

    out = DATA_DIR / "seed.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    tags = Counter(note.split(" (")[0] for r in records if r["memo"] for note in r["memo"].split(", "))
    print(f"저장: {out.name} / 문서 {len(records)}개")
    print(f"memo가 있는 날: {sum(1 for r in records if r['memo'])}일 -> {dict(tags)}")
    print("예시:", json.dumps(next(r for r in records if r["memo"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
