"""Firestore 클라이언트. 앱 전체에서 get_db() 하나로 접근한다."""
import json

import firebase_admin
from firebase_admin import credentials, firestore

from app.core.config import settings


def _credential() -> credentials.Certificate:
    # 배포(Render): JSON 문자열 / 로컬: 키 파일 경로
    if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
        return credentials.Certificate(json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON))
    if settings.FIREBASE_SERVICE_ACCOUNT_PATH:
        return credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    raise RuntimeError(
        "Firebase 서비스 계정이 설정되지 않았습니다. "
        ".env 의 FIREBASE_SERVICE_ACCOUNT_PATH 또는 FIREBASE_SERVICE_ACCOUNT_JSON 을 확인하세요."
    )


def get_db():
    if not firebase_admin._apps:
        firebase_admin.initialize_app(_credential())
    return firestore.client()
