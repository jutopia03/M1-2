/**
 * Vercel 빌드 단계에서 실행: 환경변수 API_BASE_URL -> config.js 생성
 *
 * 정적 HTML/JS는 브라우저에서 실행되므로 서버의 환경변수를 직접 읽을 수 없다.
 * 그래서 배포(빌드) 시점에 환경변수 값을 config.js 파일로 만들어 함께 배포한다.
 * 로컬에서는 config.js 가 없어도 api.js 가 http://127.0.0.1:8000 을 기본값으로 쓴다.
 */
const fs = require("fs");
const path = require("path");

const url = (process.env.API_BASE_URL || "").trim().replace(/\/+$/, "");

if (!url && process.env.VERCEL) {
  console.error("[build-config] Vercel 환경변수 API_BASE_URL 이 설정되지 않았습니다.");
  process.exit(1);
}

const config = { API_BASE_URL: url || "http://127.0.0.1:8000" };
fs.writeFileSync(path.join(__dirname, "config.js"), `window.APP_CONFIG = ${JSON.stringify(config)};\n`);
console.log("[build-config] config.js 생성:", config.API_BASE_URL);
