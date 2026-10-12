"""
data/seed.json 을 Firestore 'data' 컬렉션에 업로드한다.

- 문서 ID = 날짜(YYYY-MM-DD) -> 같은 날짜는 덮어쓰기만 되므로 여러 번 실행해도 중복이 생기지 않는다.
- Firestore 배치는 최대 500건이라 나눠서 커밋한다.

실행 (backend 폴더에서): python -m scripts.upload_seed
"""
import json
from pathlib import Path

from app.core.firebase import get_db

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed.json"
COLLECTION = "data"
BATCH_SIZE = 500


def main():
    records = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    db = get_db()
    col = db.collection(COLLECTION)

    for start in range(0, len(records), BATCH_SIZE):
        batch = db.batch()
        chunk = records[start:start + BATCH_SIZE]
        for r in chunk:
            batch.set(col.document(r["date"]), r)
        batch.commit()
        print(f"업로드 {start + len(chunk)}/{len(records)}")

    try:
        total = col.count().get()[0][0].value
    except Exception:
        total = sum(1 for _ in col.select([]).stream())
    print(f"완료: '{COLLECTION}' 컬렉션 문서 수 = {total}")


if __name__ == "__main__":
    main()
