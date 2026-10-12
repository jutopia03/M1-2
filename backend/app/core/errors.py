"""서비스 계층에서 쓰는 도메인 예외. main.py 에서 HTTP 상태 코드로 변환한다.
-> 서비스는 HTTP를 몰라도 되고, 라우터는 비즈니스 규칙을 몰라도 된다."""


class NotFoundError(Exception):
    """대상 문서가 없음 -> 404"""


class ConflictError(Exception):
    """이미 존재함 (같은 날짜 중복) -> 409"""


class InvalidDataError(Exception):
    """기존 값과 합쳤을 때 규칙 위반 (예: 수정 후 최저 > 최고) -> 422"""


class UpstreamError(Exception):
    """외부 서비스(OpenAI) 호출 실패 -> 502"""


class ServiceUnavailableError(Exception):
    """필수 설정 누락 등으로 기능을 쓸 수 없음 -> 503"""
