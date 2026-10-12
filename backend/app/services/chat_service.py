"""AI 채팅 — 컨텍스트 주입(Context Injection)

1. 데이터 요약 조회 (data_service.get_summary, 캐시됨)
2. 요약을 시스템 프롬프트에 삽입
3. 이전 대화(최근 N개)를 Firestore에서 불러와 함께 전달
4. GPT 호출
5. 질문/답변을 conversations에 자동 저장 (GPT 호출이 성공했을 때만)

/api/data/summary 를 HTTP로 다시 부르지 않고 서비스 함수를 직접 호출한다.
"""
import datetime as dt
from typing import Optional

from openai import APIError, AuthenticationError, OpenAI, RateLimitError

from app.core.config import settings
from app.core.errors import ServiceUnavailableError, UpstreamError
from app.services import conversation_service, data_service

KST = dt.timezone(dt.timedelta(hours=9))
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if not settings.OPENAI_API_KEY:
        raise ServiceUnavailableError("OPENAI_API_KEY 가 설정되지 않아 AI 채팅을 사용할 수 없습니다.")
    if _client is None:
        _client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL or None,  # None이면 공식 서버
            timeout=30,
            max_retries=1,
        )
    return _client


def _fmt_day(d: dict) -> str:
    parts = [f"평균 {d['value']}°C"]
    if d.get("min") is not None and d.get("max") is not None:
        parts.append(f"최저 {d['min']} / 최고 {d['max']}")
    if d.get("rain"):
        parts.append(f"강수 {d['rain']}mm")
    line = f"  - {d['date']}: " + ", ".join(parts)
    return line + (f" [{d['memo']}]" if d.get("memo") else "")


def _fmt_extremes(ex: dict) -> str:
    labels = [("highest_max_temp", "최고기온 최고", "°C"), ("lowest_min_temp", "최저기온 최저", "°C"),
              ("max_rain", "일강수량 최다", "mm")]
    parts = [f"{name} {ex[k]['value']}{unit} ({ex[k]['date']})" for k, name, unit in labels if ex.get(k)]
    return f"- 하루 중 기온·강수 극값: {' / '.join(parts)}\n" if parts else ""


def _fmt_yoy(yoy: dict | None) -> str:
    """진행 중인 달을 전년 같은 달 '전체'와 비교하면 일수 차이로 결론이 뒤집힐 수 있다.
    (예: 10월 1~12일 vs 작년 10월 31일 전체) -> 같은 일수끼리 비교한 값을 따로 준다."""
    if not yoy:
        return ""
    return (f"- 전년 동기 비교 (같은 일수): {yoy['month']} {yoy['compared_days']} 평균 {yoy['avg']}°C"
            f" vs {yoy['prev_month']} 같은 기간 {yoy['prev_avg']}°C (차이 {yoy['diff']:+}°C)\n")


def build_system_prompt(summary: dict, statistics: dict | None = None) -> str:
    """summary(dict)를 사람이 읽는 형태의 텍스트로 바꿔 시스템 프롬프트에 넣는다.
    JSON을 그대로 넣는 것보다 토큰이 적고 모델이 이해하기 쉽다."""
    today = dt.datetime.now(KST).date().isoformat()
    head = (
        "당신은 대전 날씨 데이터 분석 비서입니다. 사용자가 저장한 대전 일별 기온 기록"
        "(기상청 ASOS 대전 관측소)을 바탕으로 답합니다.\n"
        f"오늘 날짜: {today}\n\n"
    )
    if not summary.get("count"):
        return head + "[사용자 데이터 요약]\n- 저장된 데이터가 없습니다. 데이터가 없다고 안내하세요."

    m = summary["metrics"]
    monthly = ", ".join(f"{k}: {v['avg']}°C({v['days']}일)" for k, v in summary["monthly_avg"].items())
    recent = "\n".join(_fmt_day(d) for d in summary["recent_days"])
    return head + (
        "[사용자 데이터 요약]\n"
        f"- 데이터 기간: {summary['period']}\n"
        f"- 총 레코드: {summary['count']}개 (값: {summary['unit']})\n"
        f"- 일평균기온 기준: 전체 평균 {m['average']}°C / 가장 높았던 날 {m['max']['value']}°C ({m['max']['date']})"
        f" / 가장 낮았던 날 {m['min']['value']}°C ({m['min']['date']})\n"
        + _fmt_extremes(summary.get("extremes") or {}) +
        f"- 최근 트렌드: {summary['trend']}\n"
        f"- 월별 평균기온 (괄호는 포함 일수): {monthly}\n"
        + _fmt_yoy((statistics or {}).get("year_over_year")) +
        f"- 최근 {len(summary['recent_days'])}일 기록:\n{recent}\n\n"
        "[답변 규칙]\n"
        "1. 위 데이터에 있는 값만 근거로 답하고, 숫자를 지어내지 마세요.\n"
        "2. 최근 기록에 없는 특정 날짜의 값은 갖고 있지 않습니다. 그런 질문에는 "
        "해당 월의 평균만 알고 있다고 밝히고 월평균으로 답하세요.\n"
        "3. 데이터 기간 밖의 일(미래 예보 포함)은 알 수 없다고 말하세요.\n"
        "4. '평균기온'과 '최고/최저기온'을 구분해서 말하세요. '가장 더웠던/추웠던 날'처럼 기준이 모호하면 "
        "일평균기온 기준과 최고(최저)기온 기준을 함께 알려주세요.\n"
        "5. 비교 질문에는 구체적인 수치와 차이를 함께 제시하세요. 진행 중인(일수가 적은) 달을 작년 같은 달과 "
        "비교할 때는 월 전체 평균이 아니라 '전년 동기 비교 (같은 일수)' 값을 사용하세요.\n"
        "6. 한국어로, 2~4문장 정도로 간결하게 답하세요."
    )


def create_completion(messages: list[dict]):
    """GPT 호출 (원본 응답 반환). 점검 스크립트(scripts/check_llm.py)도 같은 함수를 쓴다.
    GPT-5 계열(추론 모델) 기준:
      - max_tokens 대신 max_completion_tokens
      - temperature 지정 불가 (기본값만 허용) -> 보내지 않음
      - reasoning_effort로 '생각' 토큰을 줄여 비용·지연을 낮춘다"""
    params = {
        "model": settings.OPENAI_MODEL,
        "messages": messages,
        "max_completion_tokens": settings.OPENAI_MAX_TOKENS,
    }
    if settings.OPENAI_REASONING_EFFORT:
        params["reasoning_effort"] = settings.OPENAI_REASONING_EFFORT
    return _get_client().chat.completions.create(**params)


def _call_openai(messages: list[dict]) -> str:
    try:
        res = create_completion(messages)
    except AuthenticationError:
        raise UpstreamError("AI 서버 인증에 실패했습니다. API 키와 OPENAI_BASE_URL을 확인하세요.")
    except RateLimitError:
        raise UpstreamError("AI 요청 한도 또는 크레딧을 초과했습니다. 잠시 후 다시 시도하세요.")
    except APIError as e:
        raise UpstreamError(f"AI 응답 생성에 실패했습니다. ({type(e).__name__}: {getattr(e, 'message', e)})")
    choice = res.choices[0]
    reply = (choice.message.content or "").strip()
    if not reply:
        if choice.finish_reason == "length":
            raise UpstreamError("AI가 답변 전에 토큰 한도를 다 썼습니다. OPENAI_MAX_TOKENS를 늘리세요.")
        raise UpstreamError("AI가 빈 응답을 반환했습니다. 다시 시도하세요.")
    return reply


def chat(message: str, conversation_id: Optional[str] = None) -> dict:
    summary = data_service.get_summary()
    statistics = data_service.get_statistics()  # 같은 캐시를 쓰므로 추가 읽기 없음

    history = []
    if conversation_id:  # 없는 ID면 여기서 404
        conv = conversation_service.get_conversation(conversation_id)
        history = conv.get("messages", [])[-settings.CHAT_HISTORY_LIMIT:]

    messages = (
        [{"role": "system", "content": build_system_prompt(summary, statistics)}]
        + [{"role": m["role"], "content": m["content"]} for m in history]
        + [{"role": "user", "content": message}]
    )
    reply = _call_openai(messages)

    now = dt.datetime.now(dt.timezone.utc)
    new_messages = [
        {"role": "user", "content": message, "created_at": now},
        {"role": "assistant", "content": reply, "created_at": now},
    ]
    if conversation_id:
        conversation_service.append_messages(conversation_id, new_messages)
    else:
        conversation_id = conversation_service.create_conversation(new_messages)["id"]
    return {"conversation_id": conversation_id, "reply": reply}
