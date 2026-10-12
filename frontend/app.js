/**
 * 화면 동작 (바닐라 JS)
 * - 채팅: 질문 전송 → 로딩 표시 → 답변 표시, 대화 목록/불러오기/삭제
 * - 요약: /api/data/summary + /api/data/statistics → 요약 카드, 추가 지표, 월별 그래프
 * - 데이터 관리: 추가/수정/삭제, 목록, CSV·JSON 내보내기
 * - 콜드스타트 대응, 다크 모드
 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const state = {
    conversationId: null,
    sending: false,
    editingId: null,
    chart: null,
    statistics: null,
    serverReady: false,
  };

  const SUGGESTIONS = [
    "가장 더웠던 날은 언제야?",
    "작년 이맘때와 비교하면 어때?",
    "최근 일주일 기온 추세는?",
    "올해 폭염은 언제 많았어?",
  ];

  // ---------- 유틸 ----------
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === false) return;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? "" : v);
    });
    (children || []).forEach((c) => c !== null && c !== undefined && node.append(c));
    return node;
  }

  // 기온은 소수 첫째 자리까지 고정 (32 -> 32.0°C)
  const fmt = (v, unit = "°C") =>
    v === null || v === undefined ? "–" : `${unit === "°C" ? Number(v).toFixed(1) : v}${unit}`;

  function fmtDateTime(iso) {
    try {
      return new Intl.DateTimeFormat("ko-KR", {
        timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
      }).format(new Date(iso));
    } catch (e) {
      return "";
    }
  }

  function todayKST() {
    return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
  }

  let toastTimer;
  function toast(message, isError) {
    const t = $("#toast");
    t.textContent = message;
    t.classList.toggle("is-error", !!isError);
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.hidden = true), isError ? 5000 : 2500);
  }

  function setStatus(kind, text) {
    const s = $("#server-status");
    s.className = `status status-${kind}`;
    s.querySelector(".status-text").textContent = text;
  }

  // ---------- 테마 ----------
  function initTheme() {
    $("#theme-toggle").addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
      if (state.statistics) renderChart(state.statistics.monthly); // 그래프 색 다시 적용
    });
  }

  // ---------- 탭 ----------
  function initTabs() {
    document.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        const name = btn.dataset.tab;
        document.querySelectorAll(".tab").forEach((b) => {
          const on = b === btn;
          b.classList.toggle("is-active", on);
          b.setAttribute("aria-selected", on);
        });
        $("#tab-chat").hidden = name !== "chat";
        $("#tab-data").hidden = name !== "data";
        if (name === "data" && state.serverReady) loadDataTable();
      });
    });
  }

  // ---------- 콜드스타트: 서버 깨우기 ----------
  async function wakeServer() {
    setStatus("pending", "서버 연결 중");
    const banner = $("#wake-banner");
    $("#wake-retry").hidden = true;
    $("#wake-text").textContent = "무료 서버가 잠들어 있어 깨우는 중입니다. 첫 연결은 최대 1분 정도 걸릴 수 있어요.";
    // 서버가 이미 깨어 있으면 배너가 깜빡이지 않도록 1.5초 뒤에만 표시
    const showTimer = setTimeout(() => (banner.hidden = false), 1500);
    try {
      await api.health(90000);
      state.serverReady = true;
      setStatus("ok", "서버 연결됨");
      banner.hidden = true;
      loadInsights();
      loadConversations();
    } catch (e) {
      setStatus("error", "연결 실패");
      banner.hidden = false;
      $("#wake-text").textContent = `서버에 연결하지 못했습니다. (${e.message})`;
      $("#wake-retry").hidden = false;
    } finally {
      clearTimeout(showTimer);
    }
  }

  // ---------- 요약 / 통계 / 그래프 ----------
  async function loadInsights() {
    try {
      const [summary, stats] = await Promise.all([api.getSummary(), api.getStatistics()]);
      state.statistics = stats;
      renderSummary(summary);
      renderStats(stats);
      renderChart(stats.monthly);
      renderMonthlyTable(stats.monthly);
    } catch (e) {
      $("#summary").replaceChildren(el("p", { class: "muted small", text: `요약을 불러오지 못했습니다: ${e.message}` }));
    }
  }

  function renderSummary(s) {
    const box = $("#summary");
    if (!s.count) {
      box.replaceChildren(el("p", { class: "muted small", text: "저장된 데이터가 없습니다." }));
      return;
    }
    const m = s.metrics || {};
    const ex = s.extremes || {};
    const row = (label, value, sub) => [
      el("dt", { text: label }),
      el("dd", {}, [value, sub ? el("small", { text: ` ${sub}` }) : null]),
    ];
    const dl = el("dl", {}, [
      ...row("기간", s.period),
      ...row("데이터 수", `${s.count.toLocaleString()}개`),
      ...row("전체 평균", fmt(m.average), "일평균"),
      ...row("일평균 최고", fmt(m.max && m.max.value), m.max && m.max.date),
      ...row("일평균 최저", fmt(m.min && m.min.value), m.min && m.min.date),
      ...row("최고기온 최고", fmt(ex.highest_max_temp && ex.highest_max_temp.value), ex.highest_max_temp && ex.highest_max_temp.date),
      ...row("최저기온 최저", fmt(ex.lowest_min_temp && ex.lowest_min_temp.value), ex.lowest_min_temp && ex.lowest_min_temp.date),
      ...row("강수 최다", fmt(ex.max_rain && ex.max_rain.value, "mm"), ex.max_rain && ex.max_rain.date),
    ]);
    const trend = el("div", { class: "trend" }, [el("strong", { text: "최근 추세" }), s.trend]);
    box.replaceChildren(dl, trend);
  }

  function renderStats(st) {
    const stat = (label, value, unit, extraClass, note) =>
      el("div", { class: `stat ${extraClass || ""}` }, [
        el("div", { class: "label", text: label }),
        el("div", { class: "value" }, [value === null || value === undefined ? "–" : String(value), el("small", { text: unit })]),
        note ? el("div", { class: "note", text: note }) : null,
      ]);
    const items = [
      stat("강수일수", st.rain_days, "일"),
      stat("평균 일교차", st.avg_daily_range, "°C"),
      stat("폭염일수 (최고 33°C↑)", st.heatwave_days, "일"),
      stat("영하일수 (최저 0°C↓)", st.freezing_days, "일"),
    ];
    const y = st.year_over_year;
    if (y) {
      const sign = y.diff > 0 ? "+" : "";
      items.push(stat(
        `전년 동월 대비 (${y.month} vs ${y.prev_month})`,
        `${sign}${y.diff}`, "°C", "wide",
        `같은 기간(${y.compared_days}) 평균 ${y.avg}°C vs ${y.prev_avg}°C`,
      ));
    }
    $("#stats").replaceChildren(...items);
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function renderChart(monthly) {
    if (!window.Chart) return; // CDN 로드 실패 시 표 보기로 대체
    const labels = monthly.map((m) => m.month.slice(2).replace("-", "."));
    const series = [
      { label: "평균최고", key: "avg_max", color: cssVar("--series-max") },
      { label: "평균", key: "avg", color: cssVar("--series-avg") },
      { label: "평균최저", key: "avg_min", color: cssVar("--series-min") },
    ];
    const text2 = cssVar("--text-2");
    const grid = cssVar("--grid");
    if (state.chart) state.chart.destroy();
    state.chart = new Chart($("#trend-chart"), {
      type: "line",
      data: {
        labels,
        datasets: series.map((s) => ({
          label: s.label,
          data: monthly.map((m) => m[s.key]),
          borderColor: s.color,
          backgroundColor: s.color,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBorderWidth: 2,
          pointHoverBorderColor: cssVar("--surface"),
          tension: 0.3,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "bottom", labels: { color: text2, boxWidth: 12, boxHeight: 2, font: { size: 12 } } },
          tooltip: {
            callbacks: {
              title: (items) => monthly[items[0].dataIndex].month + ` (${monthly[items[0].dataIndex].days}일)`,
              label: (c) => ` ${c.dataset.label}: ${c.parsed.y}°C`,
            },
          },
        },
        scales: {
          x: { ticks: { color: text2, maxRotation: 0, autoSkipPadding: 12, font: { size: 11 } }, grid: { display: false } },
          y: { ticks: { color: text2, callback: (v) => `${v}°`, font: { size: 11 } }, grid: { color: grid }, border: { display: false } },
        },
      },
    });
  }

  function renderMonthlyTable(monthly) {
    const head = el("thead", {}, [el("tr", {}, ["월", "일수", "평균", "평균최고", "평균최저", "강수합(mm)"].map((h) => el("th", { text: h })))]);
    const body = el("tbody", {}, monthly.map((m) =>
      el("tr", {}, [m.month, m.days, fmt(m.avg), fmt(m.avg_max), fmt(m.avg_min), m.rain_total].map((v) => el("td", { text: String(v) }))),
    ));
    $("#monthly-table").replaceChildren(head, body);
  }

  // ---------- 대화 목록 ----------
  async function loadConversations() {
    try {
      const list = await api.listConversations();
      const ul = $("#conv-list");
      ul.replaceChildren(...list.map((c) =>
        el("li", { class: `conv-item ${c.id === state.conversationId ? "is-active" : ""}`, "data-id": c.id }, [
          el("button", { class: "conv-open", type: "button", onclick: () => openConversation(c.id) }, [
            el("span", { class: "conv-title", text: c.title }),
            el("span", { class: "conv-meta", text: `${fmtDateTime(c.updated_at)} · 메시지 ${c.message_count}개` }),
          ]),
          el("button", {
            class: "conv-del", type: "button", title: "대화 삭제", "aria-label": `'${c.title}' 대화 삭제`,
            onclick: () => removeConversation(c.id, c.title), text: "✕",
          }),
        ]),
      ));
      $("#conv-empty").hidden = list.length > 0;
    } catch (e) {
      toast(`대화 목록을 불러오지 못했습니다: ${e.message}`, true);
    }
  }

  function markActiveConversation() {
    document.querySelectorAll(".conv-item").forEach((li) =>
      li.classList.toggle("is-active", li.dataset.id === state.conversationId));
  }

  async function openConversation(id) {
    if (state.sending) return;
    try {
      const conv = await api.getConversation(id);
      state.conversationId = conv.id;
      const box = $("#messages");
      box.replaceChildren(...conv.messages.map((m) => bubble(m.role, m.content)));
      box.scrollTop = box.scrollHeight;
      markActiveConversation();
    } catch (e) {
      toast(`대화를 불러오지 못했습니다: ${e.message}`, true);
    }
  }

  async function removeConversation(id, title) {
    if (!window.confirm(`'${title}' 대화를 삭제할까요?`)) return;
    try {
      await api.deleteConversation(id);
      if (state.conversationId === id) newChat();
      toast("대화를 삭제했습니다.");
      loadConversations();
    } catch (e) {
      toast(`삭제하지 못했습니다: ${e.message}`, true);
    }
  }

  // ---------- 채팅 ----------
  function bubble(role, text) {
    return el("div", { class: `msg msg-${role}`, text });
  }

  function newChat() {
    state.conversationId = null;
    const chips = el("div", { class: "chips" }, SUGGESTIONS.map((q) =>
      el("button", { class: "chip", type: "button", text: q, onclick: () => sendMessage(q) })));
    $("#messages").replaceChildren(el("div", { class: "empty-state" }, [
      el("h3", { text: "무엇이 궁금하세요?" }),
      el("p", { text: "저장된 대전 기온 기록(일평균·최고·최저·강수)을 바탕으로 답해 드려요." }),
      chips,
    ]));
    markActiveConversation();
    $("#chat-input").focus();
  }

  function autoResize(ta) {
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 140) + "px";
  }

  async function sendMessage(text) {
    const message = (text || "").trim();
    if (!message || state.sending) return;
    if (message.length > 1000) return toast("질문은 1000자 이내로 입력해 주세요.", true);

    const box = $("#messages");
    const input = $("#chat-input");
    const send = $("#chat-send");
    box.querySelector(".empty-state") && box.replaceChildren();
    box.append(bubble("user", message));

    const loadingText = el("span", { text: "답변을 생성하고 있어요…" });
    const loading = el("div", { class: "msg msg-assistant msg-loading" }, [
      el("span", { class: "typing", "aria-hidden": "true" }, [el("span"), el("span"), el("span")]),
      loadingText,
    ]);
    box.append(loading);
    box.scrollTop = box.scrollHeight;
    const slowTimer = setTimeout(() => {
      loadingText.textContent = "조금 오래 걸리고 있어요. 서버가 깨어나는 중이면 최대 1분 걸릴 수 있어요…";
    }, 10000);

    state.sending = true;
    input.value = "";
    autoResize(input);
    input.disabled = send.disabled = true;

    try {
      const res = await api.chat(message, state.conversationId);
      state.conversationId = res.conversation_id;
      loading.replaceWith(bubble("assistant", res.reply));
      loadConversations(); // 새 대화 추가, 목록 순서·메시지 수 갱신
    } catch (e) {
      loading.replaceWith(el("div", { class: "msg msg-error", text: `답변을 받지 못했습니다. ${e.message}` }));
      input.value = message; // 다시 보낼 수 있게 복원
      autoResize(input);
    } finally {
      clearTimeout(slowTimer);
      state.sending = false;
      input.disabled = send.disabled = false;
      input.focus();
      box.scrollTop = box.scrollHeight;
    }
  }

  function initChat() {
    const input = $("#chat-input");
    $("#chat-form").addEventListener("submit", (e) => {
      e.preventDefault();
      sendMessage(input.value);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        sendMessage(input.value);
      }
    });
    input.addEventListener("input", () => autoResize(input));
    $("#new-chat").addEventListener("click", newChat);
    $("#refresh-insights").addEventListener("click", loadInsights);
    newChat();
  }

  // ---------- 데이터 관리 ----------
  async function loadDataTable() {
    const limit = $("#data-limit").value;
    const tbody = $("#data-tbody");
    try {
      const rows = await api.listData({ order: "desc", limit });
      if (!rows.length) {
        tbody.replaceChildren(el("tr", {}, [el("td", { colspan: "7", class: "muted", text: "데이터가 없습니다." })]));
        return;
      }
      tbody.replaceChildren(...rows.map((r) =>
        el("tr", { class: r.id === state.editingId ? "is-editing" : "" }, [
          el("td", { text: r.date }),
          el("td", { text: fmt(r.value) }),
          el("td", { text: fmt(r.min) }),
          el("td", { text: fmt(r.max) }),
          el("td", { text: r.rain === null || r.rain === undefined ? "–" : String(r.rain) }),
          el("td", { class: "memo", text: r.memo || "" }),
          el("td", { class: "actions" }, [
            el("button", { class: "btn btn-small btn-ghost", type: "button", text: "수정", onclick: () => startEdit(r) }),
            el("button", { class: "btn btn-small btn-ghost btn-danger", type: "button", text: "삭제", onclick: () => removeData(r.id) }),
          ]),
        ]),
      ));
    } catch (e) {
      tbody.replaceChildren(el("tr", {}, [el("td", { colspan: "7", class: "muted", text: `불러오지 못했습니다: ${e.message}` })]));
    }
  }

  function formError(msg) {
    const p = $("#form-error");
    p.textContent = msg || "";
    p.hidden = !msg;
  }

  function startEdit(r) {
    const f = $("#data-form");
    state.editingId = r.id;
    f.date.value = r.date;
    f.date.disabled = true; // 날짜 = 문서 ID 이므로 수정 불가
    ["value", "min", "max", "rain"].forEach((k) => (f[k].value = r[k] === null || r[k] === undefined ? "" : r[k]));
    f.memo.value = r.memo || "";
    $("#form-title").textContent = `${r.date} 데이터 수정`;
    $("#form-submit").textContent = "수정 저장";
    $("#form-cancel").hidden = false;
    formError("");
    loadDataTable();
    f.value.focus();
  }

  function resetForm() {
    const f = $("#data-form");
    f.reset();
    f.date.disabled = false;
    f.date.max = todayKST();
    state.editingId = null;
    $("#form-title").textContent = "새 데이터 추가";
    $("#form-submit").textContent = "추가";
    $("#form-cancel").hidden = true;
    formError("");
  }

  function readForm() {
    const f = $("#data-form");
    const num = (name) => (f[name].value === "" ? null : Number(f[name].value));
    const payload = { value: num("value"), min: num("min"), max: num("max"), rain: num("rain"), memo: f.memo.value.trim() };
    if (payload.value === null) throw new Error("평균기온을 입력해 주세요.");
    // 서버에서도 검증하지만, 흔한 실수는 미리 안내
    if (payload.min !== null && payload.max !== null && payload.min > payload.max) throw new Error("최저기온이 최고기온보다 클 수 없습니다.");
    if (!state.editingId) {
      if (!f.date.value) throw new Error("날짜를 선택해 주세요.");
      payload.date = f.date.value;
      ["min", "max", "rain"].forEach((k) => payload[k] === null && delete payload[k]); // 추가 시 빈 값은 생략
    }
    return payload;
  }

  async function submitData(e) {
    e.preventDefault();
    let payload;
    try {
      payload = readForm();
    } catch (err) {
      return formError(err.message);
    }
    const btn = $("#form-submit");
    btn.disabled = true;
    try {
      if (state.editingId) {
        await api.updateData(state.editingId, payload);
        toast(`${state.editingId} 데이터를 수정했습니다.`);
      } else {
        await api.createData(payload);
        toast(`${payload.date} 데이터를 추가했습니다.`);
      }
      resetForm();
      loadDataTable();
      loadInsights(); // 요약·그래프에 바로 반영
    } catch (err) {
      formError(err.message);
    } finally {
      btn.disabled = false;
    }
  }

  async function removeData(id) {
    if (!window.confirm(`${id} 데이터를 삭제할까요?`)) return;
    try {
      await api.deleteData(id);
      if (state.editingId === id) resetForm();
      toast(`${id} 데이터를 삭제했습니다.`);
      loadDataTable();
      loadInsights();
    } catch (e) {
      toast(`삭제하지 못했습니다: ${e.message}`, true);
    }
  }

  // ---------- 내보내기 ----------
  function download(filename, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = el("a", { href: url, download: filename });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function exportData(kind) {
    try {
      const rows = await api.listData({ order: "asc" });
      const stamp = todayKST().replaceAll("-", "");
      const cols = ["date", "value", "min", "max", "rain", "memo"];
      if (kind === "json") {
        const clean = rows.map((r) => Object.fromEntries(cols.map((c) => [c, r[c] ?? null])));
        download(`daejeon-temperature-${stamp}.json`, JSON.stringify(clean, null, 2), "application/json");
      } else {
        const esc = (v) => {
          const s = v === null || v === undefined ? "" : String(v);
          return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
        };
        const csv = [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\r\n");
        // BOM: 엑셀에서 한글 메모가 깨지지 않도록
        download(`daejeon-temperature-${stamp}.csv`, "﻿" + csv, "text/csv;charset=utf-8");
      }
      toast(`${rows.length}건을 ${kind.toUpperCase()}로 내보냈습니다.`);
    } catch (e) {
      toast(`내보내지 못했습니다: ${e.message}`, true);
    }
  }

  function initData() {
    resetForm();
    $("#data-form").addEventListener("submit", submitData);
    $("#form-cancel").addEventListener("click", () => {
      resetForm();
      loadDataTable();
    });
    $("#data-limit").addEventListener("change", loadDataTable);
    $("#export-csv").addEventListener("click", () => exportData("csv"));
    $("#export-json").addEventListener("click", () => exportData("json"));
  }

  // ---------- 시작 ----------
  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initTabs();
    initChat();
    initData();
    $("#wake-retry").addEventListener("click", wakeServer);
    wakeServer();
  });
})();
