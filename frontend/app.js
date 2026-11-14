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
        ${item("settings", "ตั้งค่า")}
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
          <p><strong>สิ่งที่เก็บ</strong> ข้อความที่คุณพิมพ์ในแชท (ระบบลบเบอร์โทร อีเมล ไลน์ ชื่อ และชื่อโรงเรียนออกให้ก่อน) คำตอบของแชทบอท ผลแบบประเมิน 9Q และคะแนนความพึงพอใจ</p>
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

        <div class="divider" role="separator">หรือ</div>

        <button class="btn btn-secondary btn-block" id="anonymous-btn" type="button">🕶️ เข้าใช้งานแบบไม่ระบุตัวตน</button>
        <p class="subtitle" style="margin-top:0.5rem;font-size:0.82rem">
          ไม่ต้องกรอกชื่อ อีเมล หรือรหัสผ่าน ระบบจะไม่รู้ว่าคุณเป็นใคร แต่ยังบันทึกผลการประเมินและ
          ประวัติแชทให้ระหว่างที่ใช้งานอยู่ — ข้อควรรู้: ถ้าล้างข้อมูลเบราว์เซอร์หรือเปลี่ยนเครื่อง
          จะไม่สามารถกลับเข้าบัญชีนี้ได้อีก เพราะไม่มีอีเมล/รหัสผ่านให้ล็อกอินซ้ำ
        </p>
        <p class="error-text" id="anon-error" hidden></p>
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

  app.querySelector("#anonymous-btn").addEventListener("click", async (e) => {
    const btn = e.target;
    const errorEl = app.querySelector("#anon-error");
    errorEl.hidden = true;
    btn.disabled = true;
    btn.textContent = "กำลังเข้าใช้งาน...";
    try {
      const data = await api("POST", "/auth/anonymous", { ...(state.research || {}) });
      setAuth(data.token, data.user);
      navigate("dashboard");
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
      btn.disabled = false;
      btn.textContent = "🕶️ เข้าใช้งานแบบไม่ระบุตัวตน";
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
async function renderDashboard() {
  wrap(`<p class="subtitle">กำลังโหลด...</p>`);
  try {
    const [me, history, notifications] = await Promise.all([
      api("GET", "/users/me"),
      api("GET", "/assessments"),
      api("GET", "/notifications"),
    ]);
    const latest = history[0] || null;
    const unread = notifications.filter((n) => n.status !== "read");

    wrap(`
      <h1>สวัสดีค่ะ ${escapeHtml(me.display_name)} 👋</h1>
      <p class="subtitle">มาดูแลสุขภาพใจของคุณไปด้วยกันวันนี้</p>

      ${latest && latest.self_harm_risk_flag ? hotlineBannerHtml("ผลการประเมินล่าสุดของคุณมีสัญญาณที่ควรได้รับการดูแลโดยเร็ว") : ""}

      ${unread.length > 0 ? `<div class="notice">🔔 คุณมีการแจ้งเตือนที่ยังไม่ได้อ่าน ${unread.length} รายการ — ${escapeHtml(unread[0].title)}</div>` : ""}

      <div class="card">
        <h2>ผลการประเมินล่าสุด</h2>
        ${
          latest
            ? `<p style="margin-bottom:0.4rem">คะแนน <strong>${latest.total_score}/27</strong>
                <span class="badge ${SEVERITY_BADGE[latest.severity_level]}">${SEVERITY_LABEL[latest.severity_level]}</span></p>
               <p class="subtitle" style="margin-bottom:0.8rem">ทำเมื่อ ${fmtDate(latest.completed_at)}</p>
               <a href="#" class="btn btn-secondary" data-nav="history">ดูประวัติทั้งหมด</a>`
            : `<p class="subtitle">คุณยังไม่เคยทำแบบประเมิน 9Q เลย ลองเริ่มทำแบบประเมินแรกของคุณได้เลย</p>`
        }
      </div>

      <div class="card" style="display:flex;flex-direction:column;gap:0.75rem">
        <h2>เริ่มต้นใช้งาน</h2>
        <a class="btn" href="#" data-nav="assessment">📋 ทำแบบประเมิน 9Q</a>
        <a class="btn btn-secondary" href="#" data-nav="chat">💬 คุยกับแชทบอท</a>
        <a class="btn btn-secondary" href="#" data-nav="settings">⏰ ตั้งค่าแจ้งเตือนรายสัปดาห์</a>
      </div>
    `);
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
async function renderHistory() {
  wrap(`<p class="subtitle">กำลังโหลด...</p>`);
  const items = await api("GET", "/assessments");

  wrap(`
    <h1>ประวัติการทำแบบประเมิน</h1>
    <p class="subtitle">บันทึกผลการทำแบบประเมิน 9Q ของคุณทุกครั้ง เรียงจากล่าสุดไปเก่าสุด</p>
    <div class="card">
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
