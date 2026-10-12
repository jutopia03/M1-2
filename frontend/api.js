/**
 * 백엔드 API 호출 모음.
 * API 주소는 config.js(Vercel 빌드 시 환경변수로 생성)에서 읽고, 없으면 로컬 서버를 쓴다.
 */
(function () {
  const BASE = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000").replace(/\/+$/, "");

  class ApiError extends Error {
    constructor(status, message) {
      super(message);
      this.status = status;
    }
  }

  // FastAPI 오류 응답(detail)을 사람이 읽을 문장으로
  function formatDetail(detail) {
    if (!detail) return "";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const field = Array.isArray(d.loc) ? d.loc.filter((x) => x !== "body").join(".") : "";
          const msg = String(d.msg || "").replace(/^Value error, /, "");
          return field ? `${field}: ${msg}` : msg;
        })
        .join(" / ");
    }
    return JSON.stringify(detail);
  }

  async function request(path, { method = "GET", body, timeout = 60000 } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const res = await fetch(BASE + path, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json" } : {},
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new ApiError(res.status, formatDetail(data && data.detail) || `요청에 실패했습니다. (${res.status})`);
      }
      return data;
    } catch (e) {
      if (e instanceof ApiError) throw e;
      if (e.name === "AbortError") throw new ApiError(0, "서버 응답이 너무 늦습니다. 잠시 후 다시 시도해 주세요.");
      throw new ApiError(0, "서버에 연결할 수 없습니다. 네트워크 또는 서버 상태를 확인해 주세요.");
    } finally {
      clearTimeout(timer);
    }
  }

  function query(params) {
    const q = new URLSearchParams();
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.set(k, v);
    });
    const s = q.toString();
    return s ? `?${s}` : "";
  }

  window.api = {
    BASE,
    ApiError,
    health: (timeout) => request("/", { timeout }),
    getSummary: () => request("/api/data/summary"),
    getStatistics: () => request("/api/data/statistics"),
    listData: (params) => request("/api/data" + query(params)),
    createData: (payload) => request("/api/data", { method: "POST", body: payload }),
    updateData: (id, payload) => request(`/api/data/${encodeURIComponent(id)}`, { method: "PUT", body: payload }),
    deleteData: (id) => request(`/api/data/${encodeURIComponent(id)}`, { method: "DELETE" }),
    listConversations: () => request("/api/conversations"),
    getConversation: (id) => request(`/api/conversations/${encodeURIComponent(id)}`),
    deleteConversation: (id) => request(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
    chat: (message, conversationId) =>
      request("/api/chat", {
        method: "POST",
        body: conversationId ? { message, conversation_id: conversationId } : { message },
        timeout: 90000, // 콜드스타트 + AI 응답 시간 고려
      }),
  };
})();
