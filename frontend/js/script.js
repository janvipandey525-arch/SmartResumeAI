/* =========================================================
   SmartResumeAI — script.js
   The single shared frontend runtime for every page.

   Responsibilities:
     - session via Supabase Auth (window.sb) + authenticated fetch wrapper
     - auth guards + logout
     - signup / login              -> Supabase GoTrue (client-side)
     - dashboard stats + greeting  -> /api/auth/me, /api/resumes/stats
     - resume builder save         -> POST/PUT /api/resumes
     - template pick + preview/PDF  (renders the saved resume)
     - profile view + edit         -> /api/auth/me, /api/resumes
     - ATS analyzer                -> /api/ats/analyze[-file]

   No secrets live here. The Gemini key stays server-side; the UI only ever
   sees the score + text the backend chooses to return.
   Depends on js/config.js for window.apiUrl().
   ========================================================= */
(function () {
  "use strict";

  /* ------------------------------------------------------------------ */
  /* Session + local cache helpers                                      */
  /*                                                                    */
  /* The auth session (JWT, refresh) is owned entirely by supabase-js   */
  /* (window.sb). We only cache the user's profile + last resume for a  */
  /* snappier UI. `__session` is the cached Supabase session, refreshed */
  /* at boot and via onAuthStateChange so the sync guards can use it.   */
  /* ------------------------------------------------------------------ */
  const K = {
    user: "sra_user",
    rid: "sra_last_resume_id",
    cache: "sra_resume_cache",
    tpl: "sra_template",
  };

  let __session = null; // set at boot from sb.auth.getSession()

  async function getToken() {
    if (!window.sb) return null;
    const { data } = await window.sb.auth.getSession();
    return data && data.session ? data.session.access_token : null;
  }

  const store = {
    setUser(user) {
      if (user) localStorage.setItem(K.user, JSON.stringify(user));
    },
    user() {
      try { return JSON.parse(localStorage.getItem(K.user) || "null"); }
      catch { return null; }
    },
    clear() { Object.values(K).forEach((k) => localStorage.removeItem(k)); },
    lastResumeId() {
      const v = localStorage.getItem(K.rid);
      return v ? parseInt(v, 10) : null;
    },
    setLastResume(r) {
      if (r && r.id) {
        localStorage.setItem(K.rid, String(r.id));
        localStorage.setItem(K.cache, JSON.stringify(r));
      }
    },
    resumeCache() {
      try { return JSON.parse(localStorage.getItem(K.cache) || "null"); }
      catch { return null; }
    },
    template() { return localStorage.getItem(K.tpl) || "modern"; },
    setTemplate(t) { if (t) localStorage.setItem(K.tpl, t); },
  };

  async function logout() {
    try { if (window.sb) await window.sb.auth.signOut(); } catch (_) {}
    store.clear();
    location.href = "login.html";
  }

  /* ------------------------------------------------------------------ */
  /* Tiny DOM + utility helpers                                         */
  /* ------------------------------------------------------------------ */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const val = (id) => (($("#" + id) || {}).value || "").trim();
  const setVal = (id, v) => { const el = $("#" + id); if (el) el.value = v || ""; };
  const setText = (sel, v) => { const el = $(sel); if (el) el.textContent = v; };
  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
  const cssVar = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#3b6ef5";
  const esc = (s) =>
    String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  /* ------------------------------------------------------------------ */
  /* Authenticated fetch wrapper                                        */
  /* ------------------------------------------------------------------ */
  async function api(path, opts = {}) {
    const { method = "GET", body = null, auth = true, form = false } = opts;
    const headers = {};
    const init = { method, headers };
    if (auth) {
      const tok = await getToken();
      if (tok) headers.Authorization = "Bearer " + tok;
    }
    if (body != null) {
      if (form) {
        init.body = body; // FormData -> browser sets multipart boundary
      } else {
        headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(body);
      }
    }

    const res = await fetch(window.apiUrl(path), init);
    let data = null;
    if ((res.headers.get("content-type") || "").includes("application/json")) {
      data = await res.json().catch(() => null);
    }
    if (!res.ok) {
      let msg = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
      if (Array.isArray(msg)) msg = msg.map((e) => e.msg || e).join(", ");
      const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  // On a 401 the token is stale/invalid -> sign out + bounce to login.
  function handleAuthError(err) {
    if (err && err.status === 401) {
      logout();
      return true;
    }
    return false;
  }

  /* ------------------------------------------------------------------ */
  /* Toast notifications                                                */
  /* ------------------------------------------------------------------ */
  let toastBox = null;
  function toast(message, type = "info") {
    if (!toastBox) {
      toastBox = document.createElement("div");
      toastBox.id = "sraToasts";
      toastBox.style.cssText =
        "position:fixed;top:18px;right:18px;z-index:9999;display:flex;flex-direction:column;gap:10px;max-width:320px";
      document.body.appendChild(toastBox);
    }
    const colors = { info: "#2563eb", success: "#16a34a", error: "#ef4444" };
    const t = document.createElement("div");
    t.textContent = message;
    t.style.cssText =
      `background:#fff;border-left:4px solid ${colors[type] || colors.info};` +
      "box-shadow:0 8px 24px rgba(19,26,43,.14);border-radius:10px;padding:12px 16px;" +
      "font-size:.88rem;color:#131a2b;opacity:0;transform:translateX(12px);transition:.25s";
    toastBox.appendChild(t);
    requestAnimationFrame(() => { t.style.opacity = "1"; t.style.transform = "none"; });
    setTimeout(() => {
      t.style.opacity = "0";
      t.style.transform = "translateX(12px)";
      setTimeout(() => t.remove(), 300);
    }, 3800);
  }

  function btnBusy(btn, busyLabel) {
    if (!btn) return () => {};
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = busyLabel;
    return () => { btn.disabled = false; btn.innerHTML = original; };
  }

  /* ------------------------------------------------------------------ */
  /* Auth guards                                                        */
  /* ------------------------------------------------------------------ */
  // Guards read the cached __session set at boot (see the boot block), so they
  // stay synchronous for the per-page init functions.
  function requireAuth() {
    if (!__session) { location.href = "login.html"; return false; }
    return true;
  }
  function redirectIfAuthed() {
    if (__session) location.href = "dashboard.html";
  }

  /* ------------------------------------------------------------------ */
  /* Shared chrome: navbar toggle, sidebar toggle, logout               */
  /* ------------------------------------------------------------------ */
  function wireChrome() {
    const navToggle = $("#navToggle");
    const navLinks = $("#navLinks");
    if (navToggle && navLinks) {
      navToggle.addEventListener("click", () => navLinks.classList.toggle("open"));
    }

    const sbToggle = $("#sidebarToggle");
    const sidebar = $("#sidebar");
    const backdrop = $("#sidebarBackdrop");
    if (sbToggle && sidebar) {
      const toggle = () => {
        sidebar.classList.toggle("open");
        if (backdrop) backdrop.classList.toggle("show");
      };
      sbToggle.addEventListener("click", toggle);
      if (backdrop) backdrop.addEventListener("click", toggle);
    }

    // Logout: any sidebar-foot link that points at login.html clears the session.
    $$(".sidebar-foot a").forEach((a) => {
      if ((a.getAttribute("href") || "").includes("login")) {
        a.addEventListener("click", (e) => {
          e.preventDefault();
          logout();
        });
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* SIGNUP                                                             */
  /* ------------------------------------------------------------------ */
  function initSignup() {
    const form = $("#signupForm");
    if (!form) return;
    redirectIfAuthed();

    const msgEl = $("#signupMessage");
    const setMsg = (text, type) => {
      if (!msgEl) return;
      msgEl.textContent = text || "";
      msgEl.className = "form-message" + (type ? " " + type : "");
      msgEl.style.display = text ? "block" : "none";
      msgEl.style.color = type === "error" ? "var(--red)" : "var(--green)";
    };

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const full_name = val("fullname");
      const email = val("email");
      const username = val("username");
      const password = ($("#password") || {}).value || "";
      const confirm = ($("#confirmPassword") || {}).value || "";
      const terms = ($("#terms") || {}).checked;

      setMsg("");
      if (!full_name || !email || !username || !password) return setMsg("Please fill in all fields.", "error");
      if (password.length < 6) return setMsg("Password must be at least 6 characters.", "error");
      if (password !== confirm) return setMsg("Passwords do not match.", "error");
      if (!terms) return setMsg("Please accept the Terms to continue.", "error");

      if (!window.sb) return setMsg("Service unavailable. Try again shortly.", "error");

      const done = btnBusy(form.querySelector("button[type=submit]"), "Creating…");
      try {
        // full_name + username ride along as user_metadata; the DB trigger turns
        // them into the profile row on the server side.
        const { data, error } = await window.sb.auth.signUp({
          email,
          password,
          options: { data: { full_name, username } },
        });
        if (error) throw new Error(error.message);

        if (data.session) {
          // Email confirmation is disabled -> user is logged in immediately.
          location.href = "dashboard.html";
        } else {
          // Confirmation required -> tell them to check their inbox.
          setMsg("Account created. Check your email to confirm, then log in.", "success");
          done();
        }
      } catch (err) {
        setMsg(err.message, "error");
        done();
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* LOGIN                                                              */
  /* ------------------------------------------------------------------ */
  function initLogin() {
    const form = $("#loginForm");
    if (!form) return;
    redirectIfAuthed();

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      // Supabase authenticates by email. The field id stays "username" for
      // markup compatibility, but it holds the email address.
      const email = val("username");
      const password = ($("#password") || {}).value || "";
      if (!email || !password) return toast("Enter your email and password.", "error");
      if (!email.includes("@")) return toast("Please log in with your email address.", "error");
      if (!window.sb) return toast("Service unavailable. Try again shortly.", "error");

      const done = btnBusy(form.querySelector("button[type=submit]"), "Logging in…");
      try {
        const { error } = await window.sb.auth.signInWithPassword({ email, password });
        if (error) throw new Error(error.message);
        location.href = "dashboard.html";
      } catch (err) {
        toast(err.message || "Login failed.", "error");
        done();
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* DASHBOARD                                                          */
  /* ------------------------------------------------------------------ */
  async function initDashboard() {
    if (!$(".welcome-card")) return;
    if (!requireAuth()) return;

    const u = store.user();
    if (u && $("#welcomeName")) $("#welcomeName").textContent = (u.full_name || "there").split(" ")[0];

    try {
      const me = await api("/api/auth/me");
      store.setUser(me);
      setText("#welcomeName", (me.full_name || "there").split(" ")[0]);

      const s = await api("/api/resumes/stats");
      setText("#statResumes", s.resumes_created);
      setText("#statScore", s.latest_score != null ? s.latest_score : "--");
    } catch (err) {
      if (!handleAuthError(err)) toast(err.message, "error");
    }
  }

  /* ------------------------------------------------------------------ */
  /* RESUME BUILDER                                                     */
  /* ------------------------------------------------------------------ */
  function collectResume() {
    const name = val("fullName");
    const skills = val("skills").split(",").map((s) => s.trim()).filter(Boolean);
    const education = [{ college: val("college"), degree: val("degree"), year: val("year") }];
    return {
      title: name ? `${name}'s Resume` : "My Resume",
      personal_info: {
        name, email: val("email"), phone: val("phone"), address: val("address"),
      },
      education,
      skills,
      projects: val("projects"),
      experience: val("experience"),
      certifications: val("certifications"),
      summary: "",
      template_id: store.template(),
    };
  }

  function initBuilder() {
    const form = $("#resumeForm");
    if (!form) return;
    if (!requireAuth()) return;

    // Prefill from the last saved resume so editing is non-destructive.
    const c = store.resumeCache();
    if (c) {
      const pi = c.personal_info || {};
      setVal("fullName", pi.name); setVal("email", pi.email);
      setVal("phone", pi.phone); setVal("address", pi.address);
      const edu = (c.education && c.education[0]) || {};
      setVal("college", edu.college); setVal("degree", edu.degree); setVal("year", edu.year);
      setVal("skills", (c.skills || []).join(", "));
      setVal("projects", c.projects); setVal("experience", c.experience);
      setVal("certifications", c.certifications);
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = collectResume();
      const done = btnBusy(form.querySelector("button[type=submit]"), "Saving…");
      try {
        const rid = store.lastResumeId();
        let r;
        if (rid) {
          try {
            r = await api(`/api/resumes/${rid}`, { method: "PUT", body: payload });
          } catch (err) {
            if (err.status === 404) r = await api("/api/resumes", { method: "POST", body: payload });
            else throw err;
          }
        } else {
          r = await api("/api/resumes", { method: "POST", body: payload });
        }
        store.setLastResume(r);
        location.href = "templates.html";
      } catch (err) {
        if (!handleAuthError(err)) { toast(err.message, "error"); done(); }
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* TEMPLATES                                                          */
  /* ------------------------------------------------------------------ */
  function initTemplates() {
    const grid = $(".template-grid");
    if (!grid) return;
    if (!requireAuth()) return;

    $$(".template-card", grid).forEach((card) => {
      const name = (card.querySelector("h3")?.textContent || "Modern").trim();
      const tid = name.toLowerCase();
      const btn = card.querySelector(".btn");
      if (!btn) return;
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        store.setTemplate(tid);
        const rid = store.lastResumeId();
        if (rid) {
          try {
            const r = await api(`/api/resumes/${rid}`, { method: "PUT", body: { template_id: tid } });
            store.setLastResume(r);
          } catch (err) {
            if (handleAuthError(err)) return;
          }
        }
        location.href = "preview.html";
      });
    });
  }

  /* ------------------------------------------------------------------ */
  /* PREVIEW + PDF                                                      */
  /* ------------------------------------------------------------------ */
  function renderResume(el, r) {
    const pi = r.personal_info || {};
    const edu = (r.education || []).filter(Boolean);
    const skills = r.skills || [];

    const contactBits = [];
    if (pi.email) contactBits.push(`<span><i class="fa-solid fa-envelope"></i>${esc(pi.email)}</span>`);
    if (pi.phone) contactBits.push(`<span><i class="fa-solid fa-phone"></i>${esc(pi.phone)}</span>`);
    if (pi.address) contactBits.push(`<span><i class="fa-solid fa-location-dot"></i>${esc(pi.address)}</span>`);

    const section = (title, inner) =>
      inner ? `<div class="rz-section"><h3>${title}</h3>${inner}</div>` : "";

    const eduHtml = edu.length
      ? edu.map((e) => {
          const line = [e.degree, e.college, e.year].filter(Boolean).map(esc);
          return `<p class="rz-edu-line"><strong>${line[0] || ""}</strong>${line[1] ? " — " + line[1] : ""}${line[2] ? " (" + line[2] + ")" : ""}</p>`;
        }).join("")
      : "";

    const skillsHtml = skills.length
      ? `<div class="rz-skills">${skills.map((s) => `<span class="rz-skill">${esc(s)}</span>`).join("")}</div>`
      : "";

    el.innerHTML = `
      <div class="rz-header">
        <div class="rz-name">${esc(pi.name || "Your Name")}</div>
        <div class="rz-contact">${contactBits.join("")}</div>
      </div>
      ${section("Summary", r.summary ? `<p>${esc(r.summary)}</p>` : "")}
      ${section("Skills", skillsHtml)}
      ${section("Experience", r.experience ? `<p>${esc(r.experience)}</p>` : "")}
      ${section("Projects", r.projects ? `<p>${esc(r.projects)}</p>` : "")}
      ${section("Education", eduHtml)}
      ${section("Certifications", r.certifications ? `<p>${esc(r.certifications)}</p>` : "")}
    `;
  }

  async function initPreview() {
    const paper = $("#resumePaper");
    if (!paper) return;
    if (!requireAuth()) return;

    const tpl = store.template();
    paper.className = "resume-paper tpl-" + tpl;
    setText("#previewTemplateName", cap(tpl));

    let resume = store.resumeCache();
    const rid = store.lastResumeId();
    if (rid) {
      try {
        resume = await api(`/api/resumes/${rid}`);
        store.setLastResume(resume);
      } catch (err) {
        if (handleAuthError(err)) return;
      }
    }

    if (!resume) {
      paper.innerHTML =
        "<p style='padding:40px;text-align:center;color:#64748b'>No resume yet. " +
        "<a href='buildresume.html'>Build one first</a>.</p>";
      return;
    }
    renderResume(paper, resume);
    setText("#resumePaperName", (resume.personal_info || {}).name || "resume");

    const dl = $("#downloadPdfBtn");
    if (dl) {
      dl.addEventListener("click", () => {
        const fname = ((resume.personal_info || {}).name || "resume").replace(/\s+/g, "_");
        if (window.html2pdf) {
          window.html2pdf().set({
            margin: 10,
            filename: `${fname}_Resume.pdf`,
            image: { type: "jpeg", quality: 0.98 },
            html2canvas: { scale: 2, useCORS: true },
            jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
          }).from(paper).save();
        } else {
          window.print();
        }
      });
    }
  }

  /* ------------------------------------------------------------------ */
  /* PROFILE                                                            */
  /* ------------------------------------------------------------------ */
  function fillProfile(me, resume) {
    const pi = (resume && resume.personal_info) || {};
    const edu = (resume && resume.education && resume.education[0]) || {};
    const skills = (resume && resume.skills) || [];

    setText("#profileName", (me && me.full_name) || "Guest User");
    setText("#profileEmail", (me && me.email) || pi.email || "Not added yet");
    setText("#detailName", (me && me.full_name) || pi.name || "Guest User");
    setText("#detailEmail", (me && me.email) || pi.email || "Not added yet");
    setText("#detailPhone", pi.phone || "Not added yet");
    setText("#detailCollege", edu.college || "Not added yet");

    const chipsEl = $("#skillChips");
    if (chipsEl) {
      chipsEl.innerHTML = skills.length
        ? skills.map((s) => `<span class="skill-chip">${esc(s)}</span>`).join("")
        : "<span class='kw-empty'>No skills added yet.</span>";
    }
  }

  async function initProfile() {
    if (!$(".profile-wrap")) return;
    if (!requireAuth()) return;

    let me = store.user();
    let resume = null;
    try {
      me = await api("/api/auth/me");
      store.setUser(me);
      const list = await api("/api/resumes");
      resume = (list && list[0]) || null;
      if (resume) store.setLastResume(resume);
    } catch (err) {
      if (handleAuthError(err)) return;
    }
    fillProfile(me, resume);

    const editBtn = $("#editProfileBtn");
    const panel = $("#editPanel");
    const cancel = $("#cancelEditBtn");
    const form = $("#editForm");

    if (editBtn && panel) {
      editBtn.addEventListener("click", () => {
        const pi = (resume && resume.personal_info) || {};
        const edu = (resume && resume.education && resume.education[0]) || {};
        panel.hidden = false;
        setVal("editName", (me && me.full_name) || pi.name || "");
        setVal("editEmail", (me && me.email) || pi.email || "");
        setVal("editPhone", pi.phone || "");
        setVal("editCollege", edu.college || "");
        setVal("editSkills", ((resume && resume.skills) || []).join(", "));
        panel.scrollIntoView({ behavior: "smooth" });
      });
    }
    if (cancel && panel) cancel.addEventListener("click", () => (panel.hidden = true));

    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const pi = (resume && resume.personal_info) || {};
        const edu = (resume && resume.education && resume.education[0]) || {};
        const body = {
          personal_info: {
            name: val("editName") || pi.name || "",
            email: val("editEmail") || pi.email || "",
            phone: val("editPhone"),
            address: pi.address || "",
          },
          skills: val("editSkills").split(",").map((s) => s.trim()).filter(Boolean),
          education: [{ college: val("editCollege"), degree: edu.degree || "", year: edu.year || "" }],
        };
        const done = btnBusy(form.querySelector("button[type=submit]"), "Saving…");
        try {
          const rid = store.lastResumeId();
          let r;
          if (rid) {
            try { r = await api(`/api/resumes/${rid}`, { method: "PUT", body }); }
            catch (err) {
              if (err.status === 404) {
                r = await api("/api/resumes", { method: "POST", body: { ...body, title: ((me && me.full_name) || "My") + "'s Resume" } });
              } else throw err;
            }
          } else {
            r = await api("/api/resumes", { method: "POST", body: { ...body, title: ((me && me.full_name) || "My") + "'s Resume" } });
          }
          store.setLastResume(r);
          resume = r;
          fillProfile(me, r);
          if (panel) panel.hidden = true;
          toast("Profile saved.", "success");
          done();
        } catch (err) {
          if (!handleAuthError(err)) { toast(err.message, "error"); done(); }
        }
      });
    }
  }

  /* ------------------------------------------------------------------ */
  /* ATS ANALYZER                                                       */
  /* ------------------------------------------------------------------ */
  const SUGGESTIONS = {
    keywords: "Mirror more of the job description's exact keywords — most ATS engines match literally.",
    sections: "Add the standard sections (Summary, Skills, Experience, Education, Projects) with clear headings.",
    action_verbs: "Start each bullet with a strong action verb (Built, Led, Automated, Reduced).",
    impact: "Quantify achievements with numbers and percentages (e.g. \"cut latency by 35%\").",
    readability: "Keep sentences short and use bullet points — long paragraphs hurt ATS parsing.",
  };

  function meter(valSel, barSel, v) {
    const pct = Math.round(v || 0);
    setText(valSel, pct + "%");
    const bar = $(barSel);
    if (bar) requestAnimationFrame(() => (bar.style.width = pct + "%"));
  }

  function renderSuggestions(breakdown) {
    const list = $("#suggestionList");
    const empty = $("#suggestEmpty");
    if (!list) return;
    if (empty) empty.style.display = "none";

    const weak = Object.keys(SUGGESTIONS)
      .filter((k) => (breakdown[k] || 0) < 70)
      .sort((a, b) => (breakdown[a] || 0) - (breakdown[b] || 0));

    if (!weak.length) {
      list.innerHTML =
        '<div class="suggestion-item good"><i class="fa-solid fa-circle-check"></i>' +
        "<p>Strong across the board — no major issues detected. Fine-tune with the AI feedback below.</p></div>";
      return;
    }
    list.innerHTML = weak
      .map((k) =>
        '<div class="suggestion-item"><i class="fa-solid fa-triangle-exclamation"></i>' +
        `<p>${esc(SUGGESTIONS[k])}</p></div>`)
      .join("");
  }

  function chips(sel, items, kind) {
    const el = $(sel);
    if (!el) return;
    el.innerHTML = items.length
      ? items.map((k) => `<span class="kw-chip ${kind}">${esc(k)}</span>`).join("")
      : "<span class='kw-empty'>None</span>";
  }

  function verdict(score) {
    if (score >= 80) return "Excellent — this resume is highly ATS-friendly.";
    if (score >= 60) return "Good — a few tweaks will push it higher.";
    if (score >= 40) return "Needs work — address the suggestions below.";
    return "Low score — restructure using the suggestions below.";
  }

  function formatAi(text) {
    // Gemini returns light markdown: **bold**, numbered lines. Render safely.
    const safe = esc(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    const lines = safe.split(/\n+/).map((l) => l.trim()).filter(Boolean);
    return lines
      .map((l) => (/^\d+[.)]/.test(l) || /^[-*•]/.test(l))
        ? `<p>${l.replace(/^[-*•]\s?/, "• ")}</p>`
        : `<p>${l}</p>`)
      .join("");
  }

  function renderReport(r) {
    const score = r.score || 0;
    const b = r.breakdown || {};
    const color = score >= 80 ? cssVar("--green") : score >= 60 ? cssVar("--amber") : cssVar("--red");

    const ring = $("#scoreRing");
    if (ring) ring.style.background = `conic-gradient(${color} ${score * 3.6}deg, var(--line) 0)`;
    setText("#scoreValue", score);
    setText("#scoreVerdict", `${verdict(score)} (Grade ${r.grade})`);

    meter("#mKeywordVal", "#mKeywordBar", b.keywords);
    meter("#mFormatVal", "#mFormatBar", b.action_verbs);
    meter("#mSectionVal", "#mSectionBar", b.sections);
    meter("#mReadVal", "#mReadBar", b.readability);

    const kwPanel = $("#keywordPanel");
    const matched = r.matched_keywords || [];
    const missing = r.missing_keywords || [];
    if (matched.length || missing.length) {
      if (kwPanel) kwPanel.hidden = false;
      chips("#kwMatched", matched, "matched");
      chips("#kwMissing", missing, "missing");
    } else if (kwPanel) {
      kwPanel.hidden = true;
    }

    renderSuggestions(b);

    const aiPanel = $("#aiPanel");
    const ai = $("#aiFeedback");
    if ((r.ai_feedback || "").trim()) {
      if (aiPanel) aiPanel.hidden = false;
      if (ai) ai.innerHTML = formatAi(r.ai_feedback);
    } else if (aiPanel) {
      aiPanel.hidden = true;
    }

    const sr = $(".score-box");
    if (sr) sr.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function initAts() {
    const btn = $("#analyzeBtn");
    if (!btn) return;
    if (!requireAuth()) return;

    const fileInput = $("#resumeFile");
    const fileChosen = $("#fileChosen");
    if (fileInput) {
      fileInput.addEventListener("change", () => {
        const f = fileInput.files[0];
        if (f) {
          setText("#fileName", f.name);
          if (fileChosen) fileChosen.classList.add("show");
        }
      });
    }

    btn.addEventListener("click", async () => {
      const jd = (($("#jobDescription") || {}).value || "").trim();
      const f = fileInput && fileInput.files[0];
      const rid = store.lastResumeId();
      if (!f && !rid) {
        return toast("Upload a resume file, or build a resume first.", "error");
      }

      const done = btnBusy(btn, '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing…');
      try {
        let report;
        if (f) {
          const fd = new FormData();
          fd.append("file", f);
          fd.append("job_description", jd);
          fd.append("use_ai", "true");
          report = await api("/api/ats/analyze-file", { method: "POST", body: fd, form: true });
        } else {
          report = await api("/api/ats/analyze", {
            method: "POST",
            body: { resume_id: rid, job_description: jd, use_ai: true },
          });
        }
        renderReport(report);
      } catch (err) {
        if (!handleAuthError(err)) toast(err.message || "Analysis failed.", "error");
      } finally {
        done();
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Boot                                                               */
  /* ------------------------------------------------------------------ */
  document.addEventListener("DOMContentLoaded", async () => {
    // Wait for the Supabase client, then hydrate the cached session so the sync
    // auth guards work. If Supabase failed to load, only public pages function.
    await window.SB_READY;
    if (window.sb) {
      try {
        const { data } = await window.sb.auth.getSession();
        __session = data ? data.session : null;
      } catch (_) { __session = null; }

      // Keep the cached session current (token refresh, logout in another tab).
      window.sb.auth.onAuthStateChange((_event, session) => {
        __session = session;
      });
    }

    wireChrome();
    // Each init is a no-op unless its page markers are present.
    initSignup();
    initLogin();
    initDashboard();
    initBuilder();
    initTemplates();
    initPreview();
    initProfile();
    initAts();
  });
})();
