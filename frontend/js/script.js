/*
 * SmartResumeAI — frontend logic (placeholder).
 *
 * Phase 1 foundation: this file exists so pages load without 404s and so the
 * API health check is reachable from the browser. The real logic — auth,
 * resume builder, ATS analyze, PDF download — is wired to the backend API in
 * Milestone 5, replacing the old localStorage approach entirely.
 */
(function () {
  // Smoke test: confirm the frontend can reach the backend.
  // Removed in Milestone 5 once real calls exist.
  if (window.APP_CONFIG) {
    fetch(window.apiUrl("/api/health"))
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => console.info("[SmartResumeAI] API reachable:", d))
      .catch((e) => console.warn("[SmartResumeAI] API not reachable yet:", e));
  }
})();
