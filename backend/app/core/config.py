"""환경 변수 로딩. 키 값은 코드에 두지 않고 .env(로컬) 또는 Render 환경 변수에서 읽는다."""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env 를 명시적으로 지정 (실행 위치와 무관하게 동작)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    # 비워두면 OpenAI 공식 서버. 코디세이 중계 서버 키는 https://copa.codyssey.kr/v1
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    # 출력 토큰 상한 (추론 모델은 '생각' 토큰도 여기에 포함되므로 여유 있게)
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "1500"))
    # 추론 강도(minimal/low/medium/high). 비우면 보내지 않음.
    # 코디세이 중계 서버는 이 옵션을 지원하지 않음(400 unsupported_feature) -> 기본값 비움
    OPENAI_REASONING_EFFORT: str = os.getenv("OPENAI_REASONING_EFFORT", "")
    CHAT_HISTORY_LIMIT: int = int(os.getenv("CHAT_HISTORY_LIMIT", "10"))  # GPT에 보낼 이전 메시지 수
    FIREBASE_SERVICE_ACCOUNT_JSON: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    FIREBASE_SERVICE_ACCOUNT_PATH: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")
    ALLOWED_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
    ]


settings = Settings()
