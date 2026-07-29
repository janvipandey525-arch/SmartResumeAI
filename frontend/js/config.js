/*
 * SmartResumeAI — frontend runtime config.
 *
 * API_BASE is where the frontend sends requests.
 *  - In production the FastAPI app serves this page itself (same origin), so the
 *    base is just "" and requests go to /api/... on the same domain.
 *  - In local dev you often serve the frontend on :5500 (Live Server) while the
 *    API runs on :8000 — in that case point API_BASE at the dev API URL.
 *
 * No secrets ever live here. The Gemini key stays on the server.
 */
(function () {
  const isLocalDevSplit =
    ["5500", "5501"].includes(location.port); // Live Server ports

  window.APP_CONFIG = {
    // Same-origin in prod => "". Split local dev => talk to the API on :8000.
    API_BASE: isLocalDevSplit ? "http://localhost:8000" : "",
  };

  // Convenience helper used across pages (Milestone 5 fills in the callers).
  window.apiUrl = (path) =>
    window.APP_CONFIG.API_BASE + (path.startsWith("/") ? path : "/" + path);
})();
