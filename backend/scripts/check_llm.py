"""
AI 연결 점검 스크립트 — 서버를 띄우지 않고 GPT 호출만 확인한다.

python -m scripts.check_llm --probe
    중계 서버가 어떤 옵션 조합을 지원하는지 하나씩 시험한다. (요청당 아주 짧은 답변만 요청)
python -m scripts.check_llm ["질문"]
    1단계: 짧은 인사로 연결/인증/모델 확인
    2단계: 실제 시스템 프롬프트(Firestore 데이터 요약 주입) + 질문으로 답변 품질 확인

실행 위치: backend 폴더, venv 활성화 상태
"""
import sys
import time

from openai import APIError

from app.core.config import settings
from app.services import chat_service, data_service


def header() -> None:
    print(f"서버: {settings.OPENAI_BASE_URL or 'OpenAI 공식'} / 모델: {settings.OPENAI_MODEL}"
          f" / max_completion_tokens={settings.OPENAI_MAX_TOKENS}"
          f" / reasoning_effort={settings.OPENAI_REASONING_EFFORT or '(미전송)'}")


def probe() -> None:
    client = chat_service._get_client()
    msg = [{"role": "user", "content": "'안녕'이라고만 답해."}]
    cases = [
        ("옵션 없음", {}),
        ("max_tokens", {"max_tokens": 1500}),
        ("max_completion_tokens", {"max_completion_tokens": 1500}),
        ("max_completion_tokens + reasoning_effort=minimal",
         {"max_completion_tokens": 1500, "reasoning_effort": "minimal"}),
        ("max_completion_tokens + reasoning_effort=low",
         {"max_completion_tokens": 1500, "reasoning_effort": "low"}),
    ]
    print(f"모델 {settings.OPENAI_MODEL} 옵션 지원 여부:")
    for label, extra in cases:
        t = time.time()
        try:
            res = client.chat.completions.create(model=settings.OPENAI_MODEL, messages=msg, **extra)
            u = res.usage
            d = getattr(u, "completion_tokens_details", None) if u else None
            r = getattr(d, "reasoning_tokens", None) if d else None
            out = (res.choices[0].message.content or "").strip()[:20]
            print(f"  O {label:<50} {time.time() - t:4.1f}초 출력토큰 {u.completion_tokens if u else '?'}"
                  f"(추론 {r}) 답변={out!r}")
        except APIError as e:
            print(f"  X {label:<50} {getattr(e, 'status_code', '')} {getattr(e, 'message', e)}")


def run(label: str, messages: list[dict]) -> None:
    t = time.time()
    try:
        res = chat_service.create_completion(messages)
    except APIError as e:
        print(f"\n[{label}] 실패: {getattr(e, 'status_code', '')} {getattr(e, 'message', e)}")
        print("  -> python -m scripts.check_llm --probe 로 지원 옵션을 확인하세요.")
        return
    c = res.choices[0]
    u = res.usage
    details = getattr(u, "completion_tokens_details", None) if u else None
    reasoning = getattr(details, "reasoning_tokens", None) if details else None
    print(f"\n[{label}] {time.time() - t:.1f}초 / finish_reason={c.finish_reason}")
    if u:
        print(f"  토큰: 입력 {u.prompt_tokens} / 출력 {u.completion_tokens}"
              + (f" (그중 추론 {reasoning})" if reasoning is not None else ""))
    print("  답변:", (c.message.content or "(빈 응답)").strip())


def main():
    header()
    if "--probe" in sys.argv:
        probe()
        return
    question = sys.argv[1] if len(sys.argv) > 1 else "가장 더웠던 날은 언제야?"
    run("1단계 연결", [{"role": "user", "content": "한 문장으로 인사해줘."}])
    system = chat_service.build_system_prompt(data_service.get_summary())
    run(f"2단계 데이터 질문: {question}",
        [{"role": "system", "content": system}, {"role": "user", "content": question}])


if __name__ == "__main__":
    main()
