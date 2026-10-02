/*
 * SmartResumeAI — frontend runtime config + Supabase client bootstrap.
 *
 * Responsibilities:
 *   1. Decide API_BASE (same-origin in prod, :8000 in split local dev).
 *   2. Fetch public config from /api/config (Supabase URL + anon key — NOT secret).
 *   3. Load the supabase-js SDK and create window.sb (the GoTrue/session client).
 *
 * Pages must `await window.SB_READY` before using window.sb. No secrets live here;
 * the anon key is public by design and gated by Row Level Security. The service
 * role key and Gemini key never leave the server.
 */
(function () {
  const isLocalDevSplit = ["5500", "5501"].includes(location.port); // Live Server

  window.APP_CONFIG = {
    API_BASE: isLocalDevSplit ? "http://localhost:8000" : "",
  };

  window.apiUrl = (path) =>
    window.APP_CONFIG.API_BASE + (path.startsWith("/") ? path : "/" + path);

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.async = true;
      s.onload = resolve;
      s.onerror = () => reject(new Error("Failed to load " + src));
      document.head.appendChild(s);
    });
  }

  // Pages that never touch auth. Loading the 200KB+ supabase-js bundle (plus a
  // blocking /api/config round-trip) on these just delays first paint, so skip
  // the whole bootstrap and resolve SB_READY to null. script.js already treats
  // a null client as "public page" and its auth guards never run here.
  const PUBLIC_PAGES = ["", "index.html", "index"];
  const page = location.pathname.split("/").pop();
  if (PUBLIC_PAGES.includes(page)) {
    window.SB_READY = Promise.resolve(null);
    return;
  }

  // Resolves to the Supabase client (window.sb), or null if the server has no
  // Supabase config yet. Every page awaits this before touching auth.
  window.SB_READY = (async function initSupabase() {
    let cfg;
    try {
      const res = await fetch(window.apiUrl("/api/config"));
      cfg = await res.json();
    } catch (e) {
      console.error("Could not load /api/config:", e);
      return null;
    }

    window.APP_CONFIG.SUPABASE_URL = cfg.supabaseUrl || "";
    window.APP_CONFIG.AI_ENABLED = !!cfg.aiEnabled;

    if (!cfg.supabaseUrl || !cfg.supabaseAnonKey) {
      console.error(
        "Supabase is not configured on the server. Set SUPABASE_URL and " +
          "SUPABASE_ANON_KEY in the environment."
      );
      return null;
    }

    await loadScript(
      "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.js"
    );

    window.sb = window.supabase.createClient(
      cfg.supabaseUrl,
      cfg.supabaseAnonKey,
      {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true, // handles the email-confirmation redirect
          storageKey: "sra_supabase_auth",
        },
      }
    );
    return window.sb;
  })();
})();
