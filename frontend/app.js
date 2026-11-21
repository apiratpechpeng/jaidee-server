// แอปหน้าเดียว (SPA) เขียนด้วย vanilla JavaScript ล้วนๆ ไม่มี React/build step
// ทำงานคู่กับ backend Python ที่อยู่ origin เดียวกัน (ไม่ต้องกังวลเรื่อง CORS)

const API_BASE = "/api";
const app = document.getElementById("app");

// v20 การเลือกเรื่องเก็บข้อมูลวิจัย {research_consent, age_band, guardian_ack} (null = ยังไม่ได้เลือก)
function loadResearchChoice() {
  try { return JSON.parse(localStorage.getItem("research_choice") || "null"); } catch (e) { return null; }
}
function saveResearchChoice(choice) {
  state.research = choice;
  try { localStorage.setItem("research_choice", JSON.stringify(choice)); } catch (e) { /* ใช้ต่อในหน่วยความจำ */ }
}

const state = {
  research: loadResearchChoice(),
  token: localStorage.getItem("token") || null,
  user: JSON.parse(localStorage.getItem("user") || "null"),
  view: "login",
  params: {},
};

const SEVERITY_BADGE = { none: "badge-none", mild: "badge-mild", moderate: "badge-moderate", severe: "badge-severe" };
const SEVERITY_LABEL = { none: "ไม่มีอาการ", mild: "ระดับน้อย", moderate: "ระดับปานกลาง", severe: "ระดับรุนแรง" };
const DAY_LABELS = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์"];

// ---------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------
function setAuth(token, user) {
  state.token = token;
  state.user = user;
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}

function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  navigate("login");
}

async function api(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));

  // เคยเกิดปัญหาว่า token เก่าที่ค้างอยู่ใน localStorage (เช่น เซิร์ฟเวอร์ถูกรีสตาร์ทด้วย
  // ฐานข้อมูลใหม่ หรือ session หมดอายุ) ทำให้ navbar ยังโชว์เหมือนล็อกอินอยู่ (เพราะแค่เช็คว่ามี
  // token เก็บไว้ไหม ไม่ได้เช็คว่า token นั้นยังใช้ได้จริงหรือเปล่า) แต่พอเรียก API จริงกลับโดน
  // ปฏิเสธ ทำให้หน้าจอค้างอยู่ในสภาพ "ดูเหมือนล็อกอินแต่ใช้งานไม่ได้จริง" — ถ้าเจอ 401 ระหว่างที่มี
  // token อยู่ (และไม่ใช่หน้า auth เอง เช่น login ผิดรหัสผ่าน) ให้เคลียร์ค่าที่ค้างแล้วพากลับไป
  // หน้าล็อกอินให้เลย จะได้ไม่งงว่าทำไมกดอะไรก็บอกว่าให้ล็อกอินทั้งที่หน้าตาเหมือนล็อกอินอยู่
  if (res.status === 401 && state.token && !path.startsWith("/auth/")) {
    state.token = null;
    state.user = null;
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("login");
    throw new Error("เซสชันหมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบอีกครั้ง");
  }

  if (!res.ok) throw new Error(data.error || "เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง");
  return data;
}

function navigate(view, params = {}) {
  state.view = view;
  state.params = params;
  render();
  window.scrollTo(0, 0);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function fmtDate(iso, opts = { dateStyle: "long" }) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("th-TH", opts);
}

// ป้ายข้อความลอย (toast) ที่โผล่มาแป๊บนึงแล้วหายไปเอง — ต่อ DOM เข้ากับ document.body ตรงๆ
// (ไม่ผ่าน wrap()/app.innerHTML) เพื่อไม่ให้หายไปก่อนเวลาถ้ามีการ re-render หน้าเกิดขึ้นระหว่างนั้น
function showToast(message, durationMs = 3200) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add("toast-show")); // บังคับ reflow ก่อนเพื่อให้ transition ทำงาน

  setTimeout(() => {
    toast.classList.remove("toast-show");
    toast.classList.add("toast-hide");
    setTimeout(() => toast.remove(), 350); // รอ transition จางหายจบก่อนค่อยลบออกจาก DOM จริงๆ
  }, durationMs);
}

function hotlineBannerHtml(message) {
  const text = message || "หากคุณกำลังรู้สึกไม่ปลอดภัยหรือมีความคิดทำร้ายตัวเอง คุณไม่ต้องเผชิญเรื่องนี้คนเดียว";
  return `
    <div class="hotline-banner" role="alert">
      <span class="icon" aria-hidden="true">☎️</span>
      <div class="text">${escapeHtml(text)} สายด่วนสุขภาพจิต 1323 พร้อมรับฟังตลอด 24 ชั่วโมง ไม่มีค่าใช้จ่าย</div>
      <a class="call-btn" href="tel:1323">โทร 1323</a>
    </div>`;
}

// ปุ่ม action cards จาก user_response.action_cards ของ backend (สายด่วน / ดูแลตัวเอง / ไปทำแบบประเมิน)
function actionCardsHtml(cards) {
  if (!cards || cards.length === 0) return "";
  const items = cards
    .map((c) => {
      if (c.type === "HOTLINE" && c.contact_number) {
        const tel = c.contact_number.replace(/[^0-9]/g, "");
        return `<a class="action-card action-hotline" href="tel:${tel}">☎️ ${escapeHtml(c.title)}<span class="num">${escapeHtml(c.contact_number)}</span></a>`;
      }
      if (c.type === "PHQ9_ASSESSMENT") {
        return `<a class="action-card" href="#" data-nav="assessment">📋 ${escapeHtml(c.title)}</a>`;
      }
      if (c.type === "SELF_CARE") {
        return `<details class="action-card action-selfcare">
            <summary>🌬️ ${escapeHtml(c.title)}</summary>
            <p>หายใจเข้าทางจมูกช้าๆ นับ 1-2-3-4 กลั้นไว้นับ 1-2 แล้วค่อยๆ ผ่อนออกทางปาก นับ 1-2-3-4-5-6 ทำสัก 5 รอบ สังเกตว่าไหล่และมือค่อยๆ คลายลง</p>
          </details>`;
      }
      return "";
    })
    .join("");
  return `<div class="action-cards">${items}</div>`;
}

function navbarHtml() {
  if (!state.token) return "";
  const item = (view, label) => `<a href="#" data-nav="${view}" class="${state.view === view ? "active" : ""}">${label}</a>`;
  const anonymousBadge = state.user?.is_anonymous
    ? `<span class="badge badge-anonymous" title="บัญชีนี้ไม่ผูกกับอีเมลหรือชื่อจริง ถ้าล้างข้อมูลเบราว์เซอร์จะกลับเข้าบัญชีนี้ไม่ได้อีก">🕶️ โหมดไม่ระบุตัวตน</span>`
    : "";
  return `
    <header class="navbar">
      <a href="#" data-nav="dashboard" class="brand">🌿 ใจดี</a>
      ${anonymousBadge}
      <nav>
        ${item("dashboard", "หน้าหลัก")}
        ${item("assessment", "ทำแบบประเมิน")}
        ${item("history", "ประวัติ")}
        ${item("chat", "แชทบอท")}
        ${item("journal", "บันทึก")}
        ${item("settings", "ตั้งค่า")}
        <button data-action="tour" title="ดูวิธีใช้แอปอีกครั้ง">❔ คู่มือ</button>
        <button data-action="logout">ออกจากระบบ</button>
      </nav>
    </header>`;
}

function wrap(innerHtml) {
  app.innerHTML = `<div class="app-shell">${navbarHtml()}${innerHtml}</div>`;
  bindGlobalEvents();
}

function bindGlobalEvents() {
  app.querySelectorAll("[data-nav]").forEach((el) =>
    el.addEventListener("click", (e) => {
      e.preventDefault();
      navigate(el.dataset.nav);
    })
  );
  const logoutBtn = app.querySelector('[data-action="logout"]');
  if (logoutBtn) logoutBtn.addEventListener("click", logout);
  const tourBtn = app.querySelector('[data-action="tour"]');
  if (tourBtn) tourBtn.addEventListener("click", () => startTour());
}

// ---------------------------------------------------------------------
// render dispatcher
// ---------------------------------------------------------------------
function render() {
  if (!state.token && !["login", "register", "consent"].includes(state.view)) {
    state.view = "login";
  }
  if (!state.token && !state.research) state.view = "consent"; // v20 ต้องเลือกเรื่องเก็บข้อมูลก่อนเริ่มใช้
  const renderers = {
    consent: renderConsent,
    login: renderLogin,
    register: renderRegister,
    dashboard: renderDashboard,
    assessment: renderAssessment,
    result: renderResult,
    history: renderHistory,
    chat: renderChat,
    journal: renderJournal,
    settings: renderSettings,
  };
  (renderers[state.view] || renderLogin)();
}

// ---------------------------------------------------------------------
// v20 หน้าขอความยินยอมเก็บข้อมูลเพื่อการวิจัย (แสดงก่อนเริ่มใช้ครั้งแรก)
// ---------------------------------------------------------------------
function renderConsent() {
  app.innerHTML = `
    <div class="app-shell" style="padding-top:2rem">
      <div class="card">
        <h1>ก่อนเริ่มใช้ใจดี</h1>
        <p class="subtitle">ใจดีเป็นต้นแบบในโครงงานวิทยาศาสตร์ ยังไม่ใช่บริการช่วยเหลือจริง เราอยากขออนุญาตเก็บข้อมูลการใช้งานไว้วัดผลว่าแชทบอทตอบได้ดีแค่ไหน</p>
        <div class="consent-box">
          <p><strong>สิ่งที่เก็บ</strong> ข้อความที่คุณพิมพ์ในแชทและในสมุดบันทึกความรู้สึก (ระบบลบเบอร์โทร อีเมล ไลน์ ชื่อ และชื่อโรงเรียนออกให้ก่อน) อารมณ์ที่เลือกในบันทึก คำตอบของแชทบอท ผลแบบประเมิน 9Q และคะแนนความพึงพอใจ</p>
          <p><strong>สิ่งที่ไม่เก็บ</strong> ชื่อ อีเมล วันเกิด และรหัสบัญชีจริงของคุณ ระบบใช้รหัสสุ่มแทน</p>
          <p><strong>ใครเห็น</strong> เฉพาะผู้พัฒนาโครงงานและครูที่ปรึกษา ใช้เพื่อวัดผลโครงงานเท่านั้น</p>
          <p><strong>เลือกได้เสมอ</strong> ไม่ยินยอมก็ใช้แอปได้ทุกอย่าง และเปลี่ยนใจได้ภายหลังที่หน้าตั้งค่า</p>
          <p>ถ้าพิมพ์ข้อความที่แสดงว่าอาจไม่ปลอดภัย แอปจะแสดงเบอร์สายด่วนให้ แต่ไม่มีใครเฝ้าอ่านข้อความแบบทันที ถ้าต้องการความช่วยเหลือตอนนี้ โทร <strong>1323</strong> หรือ <strong>1669</strong></p>
        </div>
        <fieldset class="field consent-age">
          <legend>อายุของคุณ</legend>
          <label class="radio"><input type="radio" name="age_band" value="under18" id="age-under18" /> ต่ำกว่า 18 ปี</label>
          <label class="radio"><input type="radio" name="age_band" value="18plus" id="age-18plus" /> 18 ปีขึ้นไป</label>
        </fieldset>
        <div class="field field-checkbox" id="guardian-row" hidden>
          <input type="checkbox" id="guardian_ack" />
          <label for="guardian_ack" style="margin:0">ผู้ปกครองของฉันรับทราบและอนุญาตให้เข้าร่วมแล้ว</label>
        </div>
        <div class="field field-checkbox">
          <input type="checkbox" id="research_consent" />
          <label for="research_consent" style="margin:0">ฉันอ่านแล้ว และยินยอมให้เก็บข้อมูลตามที่เขียนไว้ด้านบน</label>
        </div>
        <p class="error-text" id="consent-error" hidden></p>
        <button class="btn btn-block" id="consent-yes" type="button" disabled>ยินยอมและเริ่มใช้</button>
        <button class="btn btn-secondary btn-block" id="consent-no" type="button" style="margin-top:0.6rem">ใช้งานโดยไม่ให้เก็บข้อมูล</button>
      </div>
    </div>`;
  const q = (sel) => app.querySelector(sel);
  const ageBand = () => (q("#age-under18").checked ? "under18" : q("#age-18plus").checked ? "18plus" : null);
  const update = () => {
    const band = ageBand();
    q("#guardian-row").hidden = band !== "under18";
    q("#consent-yes").disabled = !(q("#research_consent").checked && (band === "18plus" || (band === "under18" && q("#guardian_ack").checked)));
  };
  ["#age-under18", "#age-18plus", "#guardian_ack", "#research_consent"].forEach((s) => q(s).addEventListener("change", update));
  const done = async (choice) => {
    saveResearchChoice(choice);
    if (state.token && state.pendingResearchSync) {
      state.pendingResearchSync = false;
      await api("PUT", "/research/consent", choice).catch(() => {});
      navigate("settings");
    } else navigate(state.token ? "dashboard" : state.research ? "login" : "consent");
  };
  q("#consent-yes").addEventListener("click", () => done({ research_consent: true, age_band: ageBand(), guardian_ack: q("#guardian_ack").checked }));
  q("#consent-no").addEventListener("click", () => done({ research_consent: false, age_band: ageBand(), guardian_ack: false }));
}

// ---------------------------------------------------------------------
// Login / Register
// ---------------------------------------------------------------------
function renderLogin() {
  app.innerHTML = `
    <div class="app-shell" style="padding-top:3rem">
      <div class="card">
        <h1>เข้าสู่ระบบ</h1>
        <p class="subtitle">ยินดีต้อนรับกลับมา</p>
        <form id="login-form">
          <div class="field"><label>อีเมล</label><input type="email" name="email" required /></div>
          <div class="field"><label>รหัสผ่าน</label><input type="password" name="password" required /></div>
          <p class="error-text" id="form-error" hidden></p>
          <button class="btn btn-block" type="submit">เข้าสู่ระบบ</button>
        </form>
        <p class="link-row">ยังไม่มีบัญชี? <a href="#" data-nav="register">สมัครสมาชิก</a></p>
      </div>
    </div>`;
  bindGlobalEvents();

  app.querySelector("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const errorEl = app.querySelector("#form-error");
    errorEl.hidden = true;
    try {
      const data = await api("POST", "/auth/login", { email: form.get("email"), password: form.get("password") });
      setAuth(data.token, data.user);
      if (state.research) await api("PUT", "/research/consent", state.research).catch(() => {});
      navigate("dashboard");
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });
}

function renderRegister() {
  app.innerHTML = `
    <div class="app-shell" style="padding-top:3rem">
      <div class="card">
        <h1>สมัครสมาชิก</h1>
        <p class="subtitle">กรอกข้อมูลส่วนตัวเบื้องต้น เพื่อเริ่มดูแลสุขภาพใจไปด้วยกัน</p>
        <form id="register-form">
          <div class="field"><label>ชื่อ / ชื่อเล่นที่ใช้แสดงในแอป</label><input name="display_name" required /></div>
          <div class="field"><label>วันเกิด</label><input type="date" name="birth_date" /></div>
          <div class="field">
            <label>เพศ</label>
            <select name="gender">
              <option value="female">หญิง</option>
              <option value="male">ชาย</option>
              <option value="other">อื่นๆ</option>
              <option value="prefer_not_to_say" selected>ไม่ต้องการระบุ</option>
            </select>
          </div>
          <div class="field"><label>อีเมล</label><input type="email" name="email" required /></div>
          <div class="field"><label>รหัสผ่าน (อย่างน้อย 8 ตัวอักษร)</label><input type="password" name="password" minlength="8" required /></div>
          <div class="field field-checkbox">
            <input type="checkbox" name="consent" id="consent" />
            <label for="consent" style="margin:0">ฉันยินยอมให้แอปเก็บและใช้ข้อมูลส่วนตัวและผลการประเมินของฉัน เพื่อวิเคราะห์และให้คำแนะนำด้านสุขภาพใจ</label>
          </div>
          <p class="error-text" id="form-error" hidden></p>
          <button class="btn btn-block" type="submit">สมัครสมาชิก</button>
        </form>
        <p class="link-row">มีบัญชีอยู่แล้ว? <a href="#" data-nav="login">เข้าสู่ระบบ</a></p>
      </div>
    </div>`;
  bindGlobalEvents();

  app.querySelector("#register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const errorEl = app.querySelector("#form-error");
    errorEl.hidden = true;
    try {
      const data = await api("POST", "/auth/register", {
        display_name: form.get("display_name"),
        birth_date: form.get("birth_date") || null,
        gender: form.get("gender"),
        email: form.get("email"),
        password: form.get("password"),
        consent: form.get("consent") === "on",
        ...(state.research || {}),
      });
      setAuth(data.token, data.user);
      navigate("dashboard");
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });
}

// ---------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------
// v30 หน้าหลักบอก "ทำอะไรต่อดี" ตามสถานะของผู้ใช้ (เรียงตามความสำคัญ แสดงไม่เกิน 2 ข้อ)
const REDO_DAYS = 7; // แนะนำให้ทำ 9Q ซ้ำทุกกี่วัน

function daysSince(iso) {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
}

function isToday(iso) {
  const d = new Date(iso), t = new Date();
  return d.getFullYear() === t.getFullYear() && d.getMonth() === t.getMonth() && d.getDate() === t.getDate();
}

function nextSteps(latest, journal) {
  const steps = [];
  // ถ้าผลล่าสุดเสี่ยง หน้าหลักมีแถบโทร 1323 สีแดงอยู่ด้านบนแล้ว จึงไม่ซ้ำในกล่องนี้
  if (!latest) {
    steps.push({ icon: "📋", title: "เริ่มจากทำแบบประเมิน 9Q", text: "ใช้เวลาประมาณ 2 นาที 9 ข้อ จะได้รู้ว่าตอนนี้ใจเราเป็นยังไง", nav: "assessment", cta: "เริ่มทำแบบประเมิน" });
  } else if (daysSince(latest.completed_at) >= REDO_DAYS) {
    steps.push({ icon: "🔁", title: "ถึงเวลาทำแบบประเมินอีกครั้ง", text: `ครั้งล่าสุดทำไปเมื่อ ${daysSince(latest.completed_at)} วันก่อน ทำซ้ำเพื่อดูว่าใจเราเปลี่ยนไปยังไง`, nav: "assessment", cta: "ทำแบบประเมินอีกครั้ง" });
  }
  if (!journal.some((j) => isToday(j.created_at))) {
    steps.push({ icon: "📝", title: "วันนี้รู้สึกยังไงบ้าง?", text: "เลือกอารมณ์ของวันนี้ แล้วเขียนสั้นๆ สักบรรทัดก็ได้ ไม่มีใครตอบกลับ เป็นพื้นที่ของคุณเอง", nav: "journal", cta: "เขียนบันทึก" });
  }
  steps.push({ icon: "💬", title: "อยากระบายหรือขอคำแนะนำ", text: "คุยกับแชทบอทได้ทุกเรื่อง ไม่ต้องเรียบเรียงให้สวย", nav: "chat", cta: "คุยกับแชทบอท" });
  return steps.slice(0, 2);
}

function nextStepsHtml(steps) {
  return `<div class="card next-steps">
      <h2>วันนี้ทำอะไรต่อดี</h2>
      ${steps.map((st, i) => `
        <div class="next-step ${i === 0 ? "primary" : ""}">
          <span class="ns-icon" aria-hidden="true">${st.icon}</span>
          <div class="ns-body"><strong>${escapeHtml(st.title)}</strong><p>${escapeHtml(st.text)}</p></div>
          ${st.href ? `<a class="btn ${i === 0 ? "" : "btn-secondary"}" href="${st.href}">${escapeHtml(st.cta)}</a>`
                    : `<a class="btn ${i === 0 ? "" : "btn-secondary"}" href="#" data-nav="${st.nav}">${escapeHtml(st.cta)}</a>`}
        </div>`).join("")}
    </div>`;
}

async function renderDashboard() {
  wrap(`<p class="subtitle">กำลังโหลด...</p>`);
  try {
    const [me, history, notifications, journal] = await Promise.all([
      api("GET", "/users/me"),
      api("GET", "/assessments"),
      api("GET", "/notifications"),
      api("GET", "/journal").catch(() => []),
    ]);
    const latest = history[0] || null;
    const unread = notifications.filter((n) => n.status !== "read");

    wrap(`
      <h1>สวัสดีค่ะ ${escapeHtml(me.display_name)} 👋</h1>
      <p class="subtitle">มาดูแลสุขภาพใจของคุณไปด้วยกันวันนี้</p>

      ${latest && latest.self_harm_risk_flag ? hotlineBannerHtml("ผลการประเมินล่าสุดของคุณบ่งชี้ว่าอาจต้องการความช่วยเหลือ") : ""}

      ${unread.length > 0 ? `<div class="notice">🔔 คุณมีการแจ้งเตือนที่ยังไม่ได้อ่าน ${unread.length} รายการ — ${escapeHtml(unread[0].title)}</div>` : ""}

      ${nextStepsHtml(nextSteps(latest, journal))}

      <div class="card">
        <h2>ผลการประเมินล่าสุด</h2>
        ${
          latest
            ? `<p style="margin-bottom:0.4rem">คะแนน <strong>${latest.total_score}/27</strong>
                <span class="badge ${SEVERITY_BADGE[latest.severity_level]}">${SEVERITY_LABEL[latest.severity_level]}</span></p>
               <p class="subtitle" style="margin-bottom:0.8rem">ทำเมื่อ ${fmtDate(latest.completed_at)}</p>
               <a href="#" class="btn btn-secondary" data-nav="history">ดูประวัติและกราฟ</a>`
            : `<p class="subtitle">คุณยังไม่เคยทำแบบประเมิน 9Q เลย ลองเริ่มทำดูได้เลยค่ะ</p>`
        }
      </div>

      <div class="card" style="display:flex;flex-direction:column;gap:0.75rem">
        <h2>เมนูทั้งหมด</h2>
        <a class="btn btn-secondary" href="#" data-nav="assessment">📋 ทำแบบประเมิน 9Q</a>
        <a class="btn btn-secondary" href="#" data-nav="chat">💬 คุยกับแชทบอท</a>
        <a class="btn btn-secondary" href="#" data-nav="journal">📝 บันทึกความรู้สึก</a>
        <a class="btn btn-secondary" href="#" data-nav="settings">⏰ ตั้งค่าแจ้งเตือนรายสัปดาห์</a>
      </div>
    `);
    maybeStartTour();
  } catch (err) {
    wrap(`<p class="error-text">${escapeHtml(err.message)}</p>`);
  }
}

// ---------------------------------------------------------------------
// Assessment
// ---------------------------------------------------------------------
async function renderAssessment() {
  wrap(`<p class="subtitle">กำลังโหลด...</p>`);
  const { questions, options } = await api("GET", "/assessments/questions");
  const answers = {}; // question_no -> option_value

  function questionsHtml() {
    return questions
      .map(
        (q) => `
      <div class="question-block">
        <p class="q-text">${q.question_no}. ${escapeHtml(q.question_text_th)}</p>
        <div class="option-row">
          ${options
            .map(
              (o) => `<button type="button" class="option-pill ${answers[q.question_no] === o.option_value ? "selected" : ""}"
                        data-qno="${q.question_no}" data-value="${o.option_value}">${escapeHtml(o.option_text_th)}</button>`
            )
            .join("")}
        </div>
      </div>`
      )
      .join("");
  }

  function paint() {
    const answeredCount = Object.keys(answers).length;
    wrap(`
      <h1>แบบประเมินโรคซึมเศร้า 9Q</h1>
      <p class="subtitle">เลือกคำตอบที่ตรงกับความรู้สึกของคุณในช่วง 2 สัปดาห์ที่ผ่านมามากที่สุด ทุกคำตอบเป็นความลับ</p>
      <div class="progress-bar"><div class="progress-fill" style="width:${(answeredCount / questions.length) * 100}%"></div></div>
      <div class="card" id="question-list">${questionsHtml()}</div>
      <p class="error-text" id="form-error" hidden></p>
      <button class="btn btn-block" id="submit-btn" ${answeredCount === questions.length ? "" : "disabled"}>
        ส่งคำตอบ (${answeredCount}/${questions.length})
      </button>
    `);

    app.querySelectorAll(".option-pill").forEach((btn) =>
      btn.addEventListener("click", () => {
        answers[Number(btn.dataset.qno)] = Number(btn.dataset.value);
        paint();
      })
    );

    const submitBtn = app.querySelector("#submit-btn");
    if (submitBtn) {
      submitBtn.addEventListener("click", async () => {
        submitBtn.disabled = true;
        submitBtn.textContent = "กำลังส่งและวิเคราะห์ผล...";
        try {
          const payload = { answers: Object.entries(answers).map(([question_no, option_value]) => ({ question_no: Number(question_no), option_value })) };
          const data = await api("POST", "/assessments", payload);
          showToast("🙏 ขอบคุณที่สละเวลาทำแบบประเมินนะคะ", 1000);
          navigate("result", { id: data.assessment_id });
        } catch (err) {
          const errorEl = app.querySelector("#form-error");
          errorEl.textContent = err.message;
          errorEl.hidden = false;
          submitBtn.disabled = false;
          submitBtn.textContent = "ส่งคำตอบอีกครั้ง";
        }
      });
    }
  }

  paint();
}

// ---------------------------------------------------------------------
// Assessment result
// ---------------------------------------------------------------------
async function renderResult() {
  wrap(`<p class="subtitle">กำลังโหลดผลการประเมิน...</p>`);
  const data = await api("GET", `/assessments/${state.params.id}`);

  wrap(`
    <h1>ผลการประเมินของคุณ</h1>
    <p class="subtitle">ทำเมื่อ ${fmtDate(data.completed_at, { dateStyle: "long", timeStyle: "short" })}</p>

    ${data.self_harm_risk_flag ? hotlineBannerHtml("คำตอบข้อ 9 ของคุณบ่งชี้ว่าคุณอาจกำลังมีความคิดทำร้ายตนเอง") : ""}
    ${actionCardsHtml(data.user_response && data.user_response.action_cards)}

    <div class="card">
      <h2>คะแนนรวม</h2>
      <p style="font-size:2rem;font-weight:700;margin:0 0 0.5rem">${data.total_score}<span style="font-size:1rem;color:var(--ink-soft);font-weight:400"> / 27</span></p>
      <span class="badge ${SEVERITY_BADGE[data.severity_level]}">${escapeHtml(data.severity_label)}</span>
    </div>

    ${
      data.analysis
        ? `<div class="card">
             <h2>บทวิเคราะห์จาก AI</h2>
             <p>${escapeHtml(data.analysis.summary_text)}</p>
             <h2 style="margin-top:1.2rem">คำแนะนำ</h2>
             <pre class="recommendation">${escapeHtml(data.analysis.recommendation_text)}</pre>
           </div>`
        : ""
    }

    <div class="card">
      <h2>คำตอบรายข้อ</h2>
      ${data.answers
        .map(
          (a) => `<div class="question-block">
            <p class="q-text" style="margin-bottom:0.2rem">${a.question_no}. ${escapeHtml(a.question_text_th)}</p>
            <p class="subtitle" style="margin:0">คำตอบ: ${escapeHtml(a.option_text_th)}</p>
          </div>`
        )
        .join("")}
    </div>

    <div style="display:flex;gap:0.75rem">
      <a class="btn" href="#" data-nav="chat">คุยกับแชทบอทต่อ</a>
      <a class="btn btn-secondary" href="#" data-nav="dashboard">กลับหน้าหลัก</a>
    </div>
  `);
}

// ---------------------------------------------------------------------
// History
// ---------------------------------------------------------------------
// v30 กราฟคะแนน 9Q ตามเวลา (SVG วาดเอง ไม่ต้องใช้ไลบรารี) แถบสีพื้นหลัง = ช่วงระดับตามเกณฑ์ 9Q
const LEVEL_BANDS = [
  { from: 0, to: 6, cls: "band-none", label: "ไม่มีอาการ" },
  { from: 7, to: 12, cls: "band-mild", label: "น้อย" },
  { from: 13, to: 18, cls: "band-moderate", label: "ปานกลาง" },
  { from: 19, to: 27, cls: "band-severe", label: "รุนแรง" },
];

function scoreChartHtml(itemsNewestFirst) {
  const items = itemsNewestFirst.slice().reverse(); // เก่า -> ใหม่ (ซ้ายไปขวา)
  const W = 420, H = 220, L = 28, R = 8, T = 8, B = 28; // กว้างพอดีจอมือถือ ตัวหนังสือไม่เล็กเกิน
  const pw = W - L - R, ph = H - T - B;
  const y = (v) => T + ph - (v / 27) * ph;
  const x = (i) => L + (items.length === 1 ? pw / 2 : (i / (items.length - 1)) * pw);
  const bands = LEVEL_BANDS.map((b) => {
    const top = y(b.to + (b.to === 27 ? 0 : 0.5)), bottom = y(b.from === 0 ? 0 : b.from - 0.5);
    return `<rect class="${b.cls}" x="${L}" y="${top}" width="${pw}" height="${bottom - top}"></rect>
            <text class="band-label" x="${W - R - 4}" y="${top + 13}" text-anchor="end">${b.label}</text>`;
  }).join("");
  const ticks = [0, 6, 12, 18, 27].map((v) => `<text class="axis" x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`).join("");
  const line = items.length > 1 ? `<polyline class="score-line" points="${items.map((it, i) => `${x(i)},${y(it.total_score)}`).join(" ")}"></polyline>` : "";
  const step = Math.max(1, Math.ceil(items.length / 6)); // ป้ายวันที่ไม่เกิน ~6 อัน กันซ้อนกัน
  const dots = items.map((it, i) => `
      <circle class="score-dot ${it.self_harm_risk_flag ? "risk" : ""}" cx="${x(i)}" cy="${y(it.total_score)}" r="5">
        <title>${fmtDate(it.completed_at, { dateStyle: "medium" })}: ${it.total_score}/27${it.self_harm_risk_flag ? " (ข้อ 9 เสี่ยง)" : ""}</title>
      </circle>
      ${i % step === 0 || i === items.length - 1 ? `<text class="axis" x="${x(i)}" y="${H - 8}" text-anchor="${items.length === 1 ? "middle" : i === 0 ? "start" : i === items.length - 1 ? "end" : "middle"}">${new Date(it.completed_at).toLocaleDateString("th-TH", { day: "numeric", month: "short" })}</text>` : ""}`).join("");
  const latest = items[items.length - 1], first = items[0];
  const diff = latest.total_score - first.total_score;
  const trend = items.length < 2 ? "ทำแบบประเมินอีกครั้งในสัปดาห์หน้า เพื่อดูแนวโน้มว่าใจเราเปลี่ยนไปยังไง"
    : diff < 0 ? `คะแนนลดลง ${-diff} คะแนนจากครั้งแรก (คะแนนน้อยลง = อาการน้อยลง)`
    : diff > 0 ? `คะแนนเพิ่มขึ้น ${diff} คะแนนจากครั้งแรก ถ้ารู้สึกหนักขึ้น ลองคุยกับคนที่ไว้ใจหรือโทร 1323`
    : "คะแนนเท่ากับครั้งแรก";
  return `<div class="card">
      <h2>กราฟคะแนนตามเวลา</h2>
      <svg class="score-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="กราฟคะแนน 9Q ${items.length} ครั้ง ล่าสุด ${latest.total_score} จาก 27">
        ${bands}${ticks}${line}${dots}
      </svg>
      <p class="subtitle" style="margin:0.6rem 0 0">${escapeHtml(trend)} · จุดสีแดง = ข้อ 9 มีความเสี่ยง</p>
    </div>`;
}

function csvCell(v) {
  const t = String(v ?? "");
  return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
}

// v30 ดาวน์โหลดประวัติเป็นไฟล์ CSV (เปิดใน Excel / Google Sheets ได้ ใส่ BOM ให้ภาษาไทยไม่เพี้ยน)
async function downloadHistoryCsv() {
  const rows = await api("GET", "/assessments/export");
  const header = ["ครั้งที่", "วันที่", "เวลา", "คะแนนรวม (0-27)", "ระดับ", "ข้อ 9 มีความเสี่ยง"]
    .concat([1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => `ข้อ ${n}`));
  const lines = [header].concat(rows.map((r, i) => {
    const d = new Date(r.completed_at);
    return [i + 1, d.toLocaleDateString("th-TH"), d.toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit" }),
            r.total_score, r.severity_label || r.severity_level, r.self_harm_risk_flag ? "ใช่" : "ไม่"]
      .concat([1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (r.answers || {})[n] ?? ""));
  }));
  const csv = "﻿" + lines.map((l) => l.map(csvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `jaidee_9Q_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function renderHistory() {
  wrap(`<p class="subtitle">กำลังโหลด...</p>`);
  const items = await api("GET", "/assessments");

  wrap(`
    <h1>ประวัติการทำแบบประเมิน</h1>
    <p class="subtitle">บันทึกผลการทำแบบประเมิน 9Q ของคุณทุกครั้ง</p>
    ${items.length > 0 ? scoreChartHtml(items) : ""}
    <div class="card">
      <div class="card-head">
        <h2 style="margin:0">ทุกครั้งที่ทำ</h2>
        ${items.length > 0 ? `<button class="btn btn-secondary" id="csv-btn" type="button">⬇️ ดาวน์โหลด CSV</button>` : ""}
      </div>
      <p class="error-text" id="csv-error" hidden></p>
      ${
        items.length === 0
          ? `<div class="empty-state"><p>ยังไม่มีประวัติการทำแบบประเมิน</p><a class="btn" href="#" data-nav="assessment">เริ่มทำแบบประเมินแรก</a></div>`
          : items
              .map(
                (item) => `
          <div class="history-item" data-nav="result" data-id="${item.assessment_id}">
            <span class="date">${fmtDate(item.completed_at, { dateStyle: "medium" })}${item.self_harm_risk_flag ? " · ⚠️ ต้องติดตาม" : ""}</span>
            <span><span class="score">${item.total_score}/27</span> <span class="badge ${SEVERITY_BADGE[item.severity_level]}">${SEVERITY_LABEL[item.severity_level]}</span></span>
          </div>`
              )
              .join("")
      }
    </div>
  `);

  app.querySelectorAll(".history-item[data-id]").forEach((el) =>
    el.addEventListener("click", () => navigate("result", { id: el.dataset.id }))
  );
  const csvBtn = app.querySelector("#csv-btn");
  if (csvBtn) csvBtn.addEventListener("click", async () => {
    const errorEl = app.querySelector("#csv-error");
    errorEl.hidden = true;
    try {
      await downloadHistoryCsv();
      showToast("ดาวน์โหลดไฟล์ CSV แล้ว");
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });
}

// ---------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------
const SATISFACTION_BUCKETS = [
  { value: "0-1", label: "0-1", hint: "ควรปรับปรุง" },
  { value: "2-3", label: "2-3", hint: "พอใช้" },
  { value: "4-5", label: "4-5", hint: "ปานกลาง" },
  { value: "6-8", label: "6-8", hint: "ดี" },
  { value: "9-10", label: "9-10", hint: "ดีมาก" },
];
const SATISFACTION_TRIGGER_COUNT = 3; // โผล่ถามหลังผู้ใช้พิมพ์ครบกี่ข้อความ

function satisfactionCardHtml() {
  return `
    <div class="card satisfaction-card" id="satisfaction-card">
      <p class="satisfaction-title">การพูดคุยนี้ช่วยคุณได้มากแค่ไหน?</p>
      <p class="subtitle" style="margin-bottom:0.9rem">ให้คะแนน 0 (ไม่ช่วยเลย) ถึง 10 (ช่วยได้มากที่สุด)</p>
      <div class="satisfaction-options">
        ${SATISFACTION_BUCKETS.map(
          (b) => `<button type="button" class="satisfaction-pill" data-bucket="${b.value}" title="${b.hint}">${b.label}</button>`
        ).join("")}
      </div>
      <button type="button" class="skip-link" id="satisfaction-skip">ข้ามไปก่อน</button>
    </div>`;
}

async function renderChat() {
  wrap(`<p class="subtitle">กำลังเริ่มบทสนทนา...</p>`);
  const conversation = await api("POST", "/chat/conversations");
  const messages = [{ message_id: "welcome", sender: "ai", content: "สวัสดีครับ ผมพร้อมรับฟังคุณอยู่ตรงนี้ วันนี้อยากเล่าอะไรให้ฟังบ้างไหมครับ?" }];
  let showHotline = false;
  const BUBBLE_DELAY_MS = 500; // หน่วงระหว่างกล่องข้อความของบอท (เดิม 700)
  let sending = false;
  let satisfactionPrompted = false; // ถามไปแล้วหรือยัง (ถามแค่ครั้งเดียวต่อบทสนทนา)
  let satisfactionResolved = false; // ตอบ (หรือกดข้าม) แล้ว ไม่ต้องโชว์การ์ดอีก
  let satisfactionSubmitting = false;

  function paint() {
    const userMessageCount = messages.filter((m) => m.sender === "user").length;
    const showSatisfaction = satisfactionPrompted && !satisfactionResolved;

    wrap(`
      <h1>แชทบอทรับฟัง</h1>
      <p class="subtitle">พื้นที่ปลอดภัยสำหรับระบายความรู้สึก บทสนทนานี้เป็นความลับ</p>
      ${showHotline ? hotlineBannerHtml() : ""}
      <div class="card">
        <div class="chat-window" id="chat-window">
          ${messages
            .map((m) => `<div class="msg ${m.sender === "user" ? "user" : "ai"}">${escapeHtml(m.content)}</div>${actionCardsHtml(m.action_cards)}`)
            .join("")}
          ${sending ? `<div class="msg ai">กำลังพิมพ์...</div>` : ""}
        </div>
        <p class="error-text" id="form-error" hidden></p>
        <form class="chat-input-row" id="chat-form">
          <input id="chat-input" placeholder="พิมพ์ข้อความของคุณที่นี่..." autocomplete="off" />
          <button class="btn" type="submit" ${sending ? "disabled" : ""}>ส่ง</button>
        </form>
      </div>
      ${showSatisfaction ? satisfactionCardHtml() : ""}
    `);
    const chatWindow = app.querySelector("#chat-window");
    if (chatWindow) chatWindow.scrollTop = chatWindow.scrollHeight;

    if (showSatisfaction) {
      const card = app.querySelector("#satisfaction-card");
      if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });

      app.querySelectorAll(".satisfaction-pill").forEach((btn) =>
        btn.addEventListener("click", async () => {
          if (satisfactionSubmitting) return;
          satisfactionSubmitting = true;
          try {
            await api("POST", `/chat/conversations/${conversation.conversation_id}/satisfaction`, { bucket: btn.dataset.bucket });
          } catch (err) {
            // ให้คะแนนไม่สำเร็จก็ไม่ต้องรบกวนผู้ใช้ต่อ แค่ปิดการ์ดไปเงียบๆ พอ
            console.warn("ส่งคะแนนความพึงพอใจไม่สำเร็จ:", err.message);
          } finally {
            satisfactionSubmitting = false;
            satisfactionResolved = true;
            paint();
          }
        })
      );

      const skipBtn = app.querySelector("#satisfaction-skip");
      if (skipBtn) skipBtn.addEventListener("click", () => {
        satisfactionResolved = true;
        paint();
      });
    }

    app.querySelector("#chat-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = app.querySelector("#chat-input");
      const text = input.value.trim();
      if (!text || sending) return;

      messages.push({ message_id: `local-${Date.now()}`, sender: "user", content: text });
      sending = true;
      paint();

      try {
        const t0 = performance.now();
        const data = await api("POST", `/chat/conversations/${conversation.conversation_id}/messages`, { content: text });
        console.log(`[jaidee] เซิร์ฟเวอร์ตอบใน ${Math.round(performance.now() - t0)} ms`);
        showHotline = data.show_hotline_banner;
        // คำตอบอาจมีหลายกล่อง: ทยอยโผล่ทีละกล่อง (หน่วงสั้นๆ) ให้เหมือนคนพิมพ์ส่งทีละข้อความ
        const aiMessages = data.ai_messages || [data.ai_message];
        // ปุ่ม action cards แสดงใต้กล่องสุดท้ายของคำตอบรอบนี้
        const cards = (data.user_response && data.user_response.action_cards) || [];
        if (cards.length > 0) aiMessages[aiMessages.length - 1] = { ...aiMessages[aiMessages.length - 1], action_cards: cards };
        // v17: กล่องแรกโผล่ทันที กล่องถัดไปหน่วงสั้นลง (500 ms) และแสดง "กำลังพิมพ์..." ระหว่างรอ ไม่ให้ดูเหมือนค้าง
        for (let i = 0; i < aiMessages.length; i++) {
          messages.push(aiMessages[i]);
          sending = i < aiMessages.length - 1; // ยังมีกล่องต่อไป -> โชว์กำลังพิมพ์
          paint();
          if (i < aiMessages.length - 1) {
            await new Promise((resolve) => setTimeout(resolve, BUBBLE_DELAY_MS));
          }
        }

        const sentCount = messages.filter((m) => m.sender === "user").length;
        if (sentCount >= SATISFACTION_TRIGGER_COUNT && !satisfactionPrompted) {
          satisfactionPrompted = true;
        }
      } catch (err) {
        const errorEl = app.querySelector("#form-error");
        if (errorEl) {
          errorEl.textContent = err.message;
          errorEl.hidden = false;
        }
      } finally {
        sending = false;
        paint();
      }
    });
  }

  paint();
}

// ---------------------------------------------------------------------
// v30 สมุดบันทึกความรู้สึก: เลือกอารมณ์ + เขียนอิสระ บอทไม่ตอบ แต่ตรวจวิกฤตทุกครั้ง
// ---------------------------------------------------------------------
const MOODS = [
  { value: 1, emoji: "😢", label: "แย่มาก" },
  { value: 2, emoji: "🙁", label: "ไม่ค่อยดี" },
  { value: 3, emoji: "😐", label: "เฉยๆ" },
  { value: 4, emoji: "🙂", label: "ดี" },
  { value: 5, emoji: "😄", label: "ดีมาก" },
];
const JOURNAL_MAX = 3000;
const moodOf = (v) => MOODS.find((m) => m.value === v) || MOODS[2];

async function renderJournal() {
  wrap(`<p class="subtitle">กำลังโหลด...</p>`);
  let entries = await api("GET", "/journal");
  let mood = null;
  let alert = null; // {cards} หลังบันทึกข้อความที่มีความเสี่ยง
  const draft = { text: "" };

  function paint() {
    const recent = entries.slice(0, 7).reverse();
    wrap(`
      <h1>บันทึกความรู้สึก</h1>
      <p class="subtitle">พื้นที่เขียนระบายของคุณเอง แชทบอทจะไม่ตอบ อ่านย้อนหลังได้ตลอด</p>
      ${alert ? hotlineBannerHtml("สิ่งที่คุณเขียนฟังดูหนักมาก คุณไม่จำเป็นต้องแบกไว้คนเดียว") + `<div style="margin-bottom:1rem">${actionCardsHtml(alert.cards)}</div>` : ""}
      <div class="card">
        <h2>วันนี้รู้สึกยังไง?</h2>
        <div class="mood-row" role="radiogroup" aria-label="อารมณ์ของวันนี้">
          ${MOODS.map((m) => `<button type="button" class="mood-pill ${mood === m.value ? "selected" : ""}" role="radio"
              aria-checked="${mood === m.value}" data-mood="${m.value}"><span class="mood-emoji" aria-hidden="true">${m.emoji}</span>${m.label}</button>`).join("")}
        </div>
        <div class="field" style="margin-top:1rem">
          <label for="journal-text">อยากเล่าอะไรก็เขียนได้เลย (ไม่บังคับ)</label>
          <textarea id="journal-text" rows="6" maxlength="${JOURNAL_MAX}" placeholder="วันนี้เกิดอะไรขึ้นบ้าง รู้สึกยังไง...">${escapeHtml(draft.text)}</textarea>
          <div class="char-count" id="char-count">${draft.text.length}/${JOURNAL_MAX}</div>
        </div>
        <p class="error-text" id="form-error" hidden></p>
        <button class="btn btn-block" id="save-journal" type="button" ${mood ? "" : "disabled"}>บันทึก</button>
        <p class="subtitle" style="font-size:0.82rem;margin:0.7rem 0 0">ถ้าเขียนว่ารู้สึกไม่ปลอดภัย แอปจะแสดงเบอร์สายด่วนให้ทันที แต่ไม่มีใครเฝ้าอ่านแบบทันที
          ${state.research && state.research.research_consent ? " · คุณยินยอมให้เก็บข้อมูลวิจัย ข้อความ (ลบชื่อ เบอร์ โรงเรียนแล้ว) จะถูกเก็บเพื่อวัดผลโครงงาน" : ""}</p>
      </div>

      ${recent.length > 1 ? `<div class="card"><h2>อารมณ์ ${recent.length} ครั้งล่าสุด</h2>
        <div class="mood-strip">${recent.map((e) => `<span title="${fmtDate(e.created_at, { dateStyle: "medium" })}: ${moodOf(e.mood).label}">
          <span class="mood-emoji">${moodOf(e.mood).emoji}</span><small>${new Date(e.created_at).toLocaleDateString("th-TH", { day: "numeric", month: "short" })}</small></span>`).join("")}</div></div>` : ""}

      <div class="card">
        <h2>บันทึกที่ผ่านมา</h2>
        ${entries.length === 0 ? `<div class="empty-state"><p>ยังไม่มีบันทึก ลองเขียนอันแรกดูนะคะ</p></div>`
          : entries.map((e) => `
            <div class="journal-item">
              <div class="journal-meta">
                <span><span class="mood-emoji" aria-hidden="true">${moodOf(e.mood).emoji}</span> ${moodOf(e.mood).label} · ${fmtDate(e.created_at, { dateStyle: "medium", timeStyle: "short" })}</span>
                <button type="button" class="skip-link" data-del="${e.entry_id}">ลบ</button>
              </div>
              ${e.content ? `<p class="journal-text">${escapeHtml(e.content)}</p>` : ""}
            </div>`).join("")}
      </div>
    `);

    const ta = app.querySelector("#journal-text");
    ta.addEventListener("input", () => {
      draft.text = ta.value;
      app.querySelector("#char-count").textContent = `${ta.value.length}/${JOURNAL_MAX}`;
    });
    app.querySelectorAll("[data-mood]").forEach((b) => b.addEventListener("click", () => {
      mood = Number(b.dataset.mood);
      paint();
      app.querySelector("#journal-text").focus();
    }));
    app.querySelector("#save-journal").addEventListener("click", async (e) => {
      const btn = e.target;
      const errorEl = app.querySelector("#form-error");
      errorEl.hidden = true;
      btn.disabled = true;
      btn.textContent = "กำลังบันทึก...";
      try {
        const data = await api("POST", "/journal", { mood, content: draft.text });
        entries = [data.entry].concat(entries);
        alert = data.show_hotline_banner ? { cards: data.action_cards } : null;
        mood = null;
        draft.text = "";
        paint();
        showToast(alert ? "บันทึกแล้ว · ถ้าตอนนี้ไม่ปลอดภัย โทร 1323 ได้เลยนะคะ" : "บันทึกแล้ว 🙏");
        window.scrollTo(0, 0);
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.hidden = false;
        btn.disabled = false;
        btn.textContent = "บันทึก";
      }
    });
    app.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
      if (!window.confirm("ลบบันทึกนี้ใช่ไหม? (ลบแล้วกู้คืนไม่ได้)")) return;
      try {
        await api("DELETE", `/journal/${b.dataset.del}`);
        entries = entries.filter((x) => x.entry_id !== b.dataset.del);
        paint();
      } catch (err) {
        showToast(err.message);
      }
    }));
  }

  paint();
}

// ---------------------------------------------------------------------
// v30 ทัวร์แนะนำการใช้งาน: โผล่ครั้งแรกหลังเข้าหน้าหลัก ดูซ้ำได้จากปุ่ม "❔ คู่มือ" บนเมนู
// ---------------------------------------------------------------------
const TOUR_STEPS = [
  { icon: "👋", title: "ยินดีต้อนรับสู่ใจดี", text: "ใจดีเป็นเพื่อนช่วยดูแลใจ ใช้ได้ทุกวัน เราจะพาดูสั้นๆ ว่าในแอปมีอะไรบ้าง (5 ขั้น กดข้ามได้)" },
  { icon: "📋", title: "แบบประเมิน 9Q", text: "9 ข้อ ใช้เวลาประมาณ 2 นาที ช่วยบอกว่าตอนนี้ใจเราอยู่ระดับไหน ผลทุกครั้งดูย้อนหลังเป็นกราฟได้ที่เมนู \"ประวัติ\" และดาวน์โหลดเป็นไฟล์ได้" },
  { icon: "💬", title: "แชทบอทรับฟัง", text: "อยากระบายหรืออยากได้คำแนะนำ พิมพ์คุยได้เลย บอทจะฟังและถามก่อน ถ้าอยากได้แนวทางให้พิมพ์ว่า \"ควรทำยังไงดี\"" },
  { icon: "📝", title: "บันทึกความรู้สึก", text: "เลือกอารมณ์ของวันนี้แล้วเขียนสั้นๆ ไว้อ่านเอง บอทไม่ตอบ ทำทุกวันจะเห็นว่าอารมณ์เราเปลี่ยนไปยังไง" },
  { icon: "☎️", title: "ถ้ารู้สึกไม่ปลอดภัย", text: "โทรสายด่วนสุขภาพจิต 1323 ได้ตลอด 24 ชั่วโมง ฟรี หรือ 1669 กรณีฉุกเฉิน ถ้าแอปเห็นข้อความที่น่าเป็นห่วงจะแสดงปุ่มโทรให้ทันที\n\nหน้าหลักมีกล่อง \"วันนี้ทำอะไรต่อดี\" คอยบอกขั้นต่อไป และกดปุ่ม ❔ คู่มือ บนเมนูเพื่อดูหน้านี้อีกครั้งได้" },
];

function tourKey() {
  return `jaidee_tour_done_${(state.user && state.user.user_id) || "guest"}`;
}

function maybeStartTour() {
  let done = false;
  try { done = localStorage.getItem(tourKey()) === "1"; } catch (e) { done = true; }
  if (!done) startTour();
}

function startTour() {
  if (document.querySelector(".tour-overlay")) return;
  let i = 0;
  const overlay = document.createElement("div");
  overlay.className = "tour-overlay";
  document.body.appendChild(overlay);
  const close = () => {
    try { localStorage.setItem(tourKey(), "1"); } catch (e) { /* ใช้ต่อได้ แค่จะโผล่อีกครั้ง */ }
    document.removeEventListener("keydown", onKey);
    overlay.remove();
  };
  const onKey = (e) => {
    if (e.key === "Escape") close();
    if (e.key === "ArrowRight" && i < TOUR_STEPS.length - 1) { i++; paint(); }
    if (e.key === "ArrowLeft" && i > 0) { i--; paint(); }
  };
  document.addEventListener("keydown", onKey);

  function paint() {
    const st = TOUR_STEPS[i], last = i === TOUR_STEPS.length - 1;
    overlay.innerHTML = `
      <div class="tour-card" role="dialog" aria-modal="true" aria-labelledby="tour-title">
        <div class="tour-icon" aria-hidden="true">${st.icon}</div>
        <h2 id="tour-title">${escapeHtml(st.title)}</h2>
        <p class="tour-text">${escapeHtml(st.text)}</p>
        <div class="tour-dots" aria-label="ขั้นที่ ${i + 1} จาก ${TOUR_STEPS.length}">
          ${TOUR_STEPS.map((_, k) => `<span class="${k === i ? "on" : ""}"></span>`).join("")}
        </div>
        <div class="tour-actions">
          ${last ? "" : `<button type="button" class="skip-link" data-t="skip">ข้าม</button>`}
          <span style="flex:1"></span>
          ${i > 0 ? `<button type="button" class="btn btn-secondary" data-t="back">ย้อนกลับ</button>` : ""}
          <button type="button" class="btn" data-t="next">${last ? "เริ่มใช้งาน" : "ถัดไป"}</button>
        </div>
      </div>`;
    overlay.querySelector('[data-t="next"]').addEventListener("click", () => { if (last) close(); else { i++; paint(); } });
    const back = overlay.querySelector('[data-t="back"]');
    if (back) back.addEventListener("click", () => { i--; paint(); });
    const skip = overlay.querySelector('[data-t="skip"]');
    if (skip) skip.addEventListener("click", close);
    overlay.querySelector('[data-t="next"]').focus();
  }
  paint();
}

// ---------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------
async function renderSettings() {
  wrap(`<p class="subtitle">กำลังโหลด...</p>`);
  const prefs = await api("GET", "/notifications/preferences");
  const research = await api("GET", "/research/consent").catch(() => null);

  wrap(`
    <h1>ตั้งค่าการแจ้งเตือน</h1>
    <p class="subtitle">เลือกวันและเวลาที่สะดวกให้แอปเตือนคุณทำแบบประเมิน 9Q ทุกสัปดาห์</p>
    <div class="card">
      <form id="settings-form">
        <div class="field field-checkbox">
          <input type="checkbox" id="reminder_enabled" ${prefs.reminder_enabled ? "checked" : ""} />
          <label for="reminder_enabled" style="margin:0">เปิดการแจ้งเตือนรายสัปดาห์</label>
        </div>
        <div class="field">
          <label>วันที่แจ้งเตือน</label>
          <select name="day_of_week">
            ${DAY_LABELS.map((label, idx) => `<option value="${idx}" ${idx === prefs.day_of_week ? "selected" : ""}>${label}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>เวลาที่แจ้งเตือน</label>
          <input type="time" name="time_of_day" value="${(prefs.time_of_day || "19:00").slice(0, 5)}" />
        </div>
        <p class="error-text" id="form-error" hidden></p>
        <button class="btn" type="submit">บันทึกการตั้งค่า</button>
        <span id="saved-msg" style="margin-left:0.8rem;color:var(--accent);font-size:0.88rem" hidden>บันทึกแล้ว ✓</span>
      </form>
    </div>
    ${research ? `
    <h2>การเก็บข้อมูลเพื่อการวิจัย</h2>
    <div class="card">
      <p class="subtitle" style="margin-top:0">${research.research_consent
        ? "ตอนนี้คุณ<strong>ยินยอม</strong>ให้เก็บข้อความแชทและผลประเมิน (ลบข้อมูลที่ระบุตัวตนออกแล้ว) เพื่อวัดผลโครงงาน"
        : "ตอนนี้ระบบ<strong>ไม่ได้เก็บ</strong>ข้อมูลการใช้งานของคุณ"}</p>
      <button class="btn btn-secondary" id="research-toggle" type="button">${research.research_consent ? "หยุดให้เก็บข้อมูล" : "เปลี่ยนเป็นยินยอม"}</button>
      <p class="subtitle" style="font-size:0.82rem">หยุดให้เก็บแล้ว ข้อมูลใหม่จะไม่ถูกเก็บอีก ถ้าอยากให้ลบข้อมูลที่เก็บไปแล้ว ติดต่อผู้พัฒนาโครงงาน</p>
    </div>` : ""}
  `);
  const toggle = app.querySelector("#research-toggle");
  if (toggle) toggle.addEventListener("click", async () => {
    if (research.research_consent) {
      const choice = { research_consent: false, age_band: research.age_band, guardian_ack: false };
      await api("PUT", "/research/consent", choice);
      saveResearchChoice(choice);
      renderSettings();
    } else {
      // ขอความยินยอมใหม่ผ่านหน้าเดิม (ต้องเลือกอายุ/ผู้ปกครองอีกครั้ง) แล้วส่งให้เซิร์ฟเวอร์ตอนกลับมา
      state.research = null;
      try { localStorage.removeItem("research_choice"); } catch (e) { /* ignore */ }
      state.pendingResearchSync = true;
      app.innerHTML = "";
      renderConsent();
    }
  });

  app.querySelector("#settings-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const errorEl = app.querySelector("#form-error");
    const savedEl = app.querySelector("#saved-msg");
    errorEl.hidden = true;
    savedEl.hidden = true;
    try {
      await api("PUT", "/notifications/preferences", {
        reminder_enabled: app.querySelector("#reminder_enabled").checked,
        day_of_week: Number(form.get("day_of_week")),
        time_of_day: form.get("time_of_day"),
      });
      savedEl.hidden = false;
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });
}

// ---------------------------------------------------------------------
// เริ่มแอป
// ---------------------------------------------------------------------
navigate(state.token ? "dashboard" : "login");
