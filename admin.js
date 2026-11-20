// หน้าผู้ดูแลของใจดี (/admin) — ดูคำตอบของผู้ใช้ที่ยินยอม สรุปผล และติดป้ายโดยผู้ตรวจ 2 คน
// ข้อความของผู้ใช้เป็นข้อมูลที่ไม่น่าไว้ใจ แสดงผ่าน esc() เสมอ (กันโค้ดแปลกๆ ในข้อความ)
const root = document.getElementById("admin");
const A = {
  token: sessionGet("admin_token"),
  rater: sessionGet("admin_rater") || "1",
  tab: "overview",
  data: { summary: null, research_chat: null, research_assessment: null, research_rating: null },
  filter: { q: "", crisis: "", topic: "", intent: "", unlabeled: false },
  conv: null,
};
const CRISIS_TH = { none: "ไม่วิกฤต", moderate: "ปานกลาง", high: "สูง" };

function sessionGet(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }
function sessionSet(k, v) { try { v === null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch (e) { /* ignore */ } }
function esc(t) { const d = document.createElement("div"); d.textContent = t ?? ""; return d.innerHTML; }
function fmtTime(t) { if (!t) return "-"; const d = new Date(t); return isNaN(d) ? esc(t) : d.toLocaleString("th-TH", { dateStyle: "short", timeStyle: "short" }); }

async function api(method, path, body) {
  const res = await fetch("/api/admin" + path, {
    method, headers: { "Content-Type": "application/json", ...(A.token ? { "X-Admin-Token": A.token } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && path !== "/login") { logout(); throw new Error("หมดเวลาเข้าสู่ระบบ กรุณาเข้าใหม่"); }
  if (!res.ok) throw new Error(data.error || "เกิดข้อผิดพลาด");
  return data;
}
function logout() { A.token = null; sessionSet("admin_token", null); renderLogin(); }

// ---------------------------------------------------------------- login
function renderLogin(msg) {
  root.innerHTML = `
    <div class="app-shell" style="padding-top:3rem;max-width:440px">
      <div class="card">
        <h1>ผู้ดูแลใจดี</h1>
        <p class="subtitle">หน้านี้แสดงข้อความของผู้ใช้ที่ยินยอมให้เก็บข้อมูล ใช้เฉพาะผู้พัฒนาโครงงานและครูที่ปรึกษา</p>
        <form id="login">
          <div class="field"><label for="pw">รหัสผู้ดูแล</label><input type="password" id="pw" autocomplete="current-password" required /></div>
          <p class="error-text" id="err" ${msg ? "" : "hidden"}>${esc(msg || "")}</p>
          <button class="btn btn-block" type="submit">เข้าสู่ระบบ</button>
        </form>
      </div>
    </div>`;
  root.querySelector("#login").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const d = await api("POST", "/login", { password: root.querySelector("#pw").value });
      A.token = d.token; sessionSet("admin_token", d.token);
      await loadAll(); renderMain();
    } catch (err) { renderLogin(err.message); }
  });
}

// ---------------------------------------------------------------- data
async function loadAll() {
  // v30 research_journal อาจยังไม่ได้สร้างใน Supabase -> ถ้าโหลดไม่ได้ให้เป็นรายการว่าง หน้าอื่นยังใช้ได้
  const [summary, chat, assess, rating, journal] = await Promise.all([
    api("GET", "/summary"), api("GET", "/rows/research_chat"), api("GET", "/rows/research_assessment"), api("GET", "/rows/research_rating"),
    api("GET", "/rows/research_journal").catch(() => []),
  ]);
  Object.assign(A.data, { summary, research_chat: chat, research_assessment: assess, research_rating: rating, research_journal: journal });
}

function toCsv(rows) {
  if (!rows.length) return "";
  const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  const cell = (v) => { const s = v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return "﻿" + [cols.join(","), ...rows.map((r) => cols.map((c) => cell(r[c])).join(","))].join("\n");
}
function download(name, rows) {
  const url = URL.createObjectURL(new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------------------------------------------------------------- layout
function renderMain() {
  const s = A.data.summary;
  const tabs = [["overview", "ภาพรวม"], ["messages", `ข้อความ (${A.data.research_chat.length})`], ["conversations", "บทสนทนา"],
                ["assessments", `แบบประเมิน (${A.data.research_assessment.length})`], ["ratings", `ความพึงพอใจ (${A.data.research_rating.length})`],
                ["journal", `บันทึกความรู้สึก (${A.data.research_journal.length})`]];
  root.innerHTML = `
    <div class="admin-shell">
      <div class="admin-top">
        <h1>ผู้ดูแลใจดี <span class="storage-chip ${s.storage === "supabase" ? "" : "local"}">${s.storage === "supabase" ? "Supabase" : "ไฟล์ในเซิร์ฟเวอร์ (ทดสอบ)"}</span></h1>
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap;align-items:center">
          <label class="muted">ฉันคือ <select id="rater"><option value="1">ผู้ตรวจ 1</option><option value="2">ผู้ตรวจ 2</option></select></label>
          <button class="small-btn ghost" id="refresh" type="button">โหลดใหม่</button>
          <button class="small-btn ghost" id="logout" type="button">ออกจากระบบ</button>
        </div>
      </div>
      ${s.storage === "supabase" ? "" : `<div class="notice">ยังไม่ได้ตั้งค่า Supabase ข้อมูลนี้อยู่ในไฟล์บนเซิร์ฟเวอร์ และจะหายเมื่อ Render รีสตาร์ต</div>`}
      <nav class="tabs">${tabs.map(([k, l]) => `<button type="button" data-tab="${k}" class="${A.tab === k ? "active" : ""}">${l}</button>`).join("")}</nav>
      <div id="tab"></div>
    </div>`;
  root.querySelector("#rater").value = A.rater;
  root.querySelector("#rater").addEventListener("change", (e) => { A.rater = e.target.value; sessionSet("admin_rater", A.rater); renderTab(); });
  root.querySelector("#logout").addEventListener("click", logout);
  root.querySelector("#refresh").addEventListener("click", async (e) => { e.target.disabled = true; try { await loadAll(); } finally { renderMain(); } });
  root.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => { A.tab = b.dataset.tab; renderMain(); }));
  renderTab();
}
function renderTab() {
  const el = root.querySelector("#tab");
  ({ overview: tabOverview, messages: tabMessages, conversations: tabConversations, assessments: tabAssessments, ratings: tabRatings, journal: tabJournal })[A.tab](el);
}

// ---------------------------------------------------------------- overview
function bars(obj, crisisKey) {
  const entries = Object.entries(obj || {}); const max = Math.max(1, ...entries.map(([, v]) => v));
  if (!entries.length) return `<p class="muted">ยังไม่มีข้อมูล</p>`;
  return `<div class="bars">${entries.slice(0, 12).map(([k, v]) => `
    <div class="bar"><span class="k" title="${esc(k)}">${esc(k)}</span><span class="track"><span class="fill ${crisisKey && k !== "NONE" && k !== "-" ? "crisis" : ""}" style="width:${(v / max) * 100}%"></span></span><span class="v">${v}</span></div>`).join("")}</div>`;
}
function tabOverview(el) {
  const s = A.data.summary, c = s.counts, L = s.labels, sv = L.system_vs_rater1;
  const pct = (x) => (x === null || x === undefined ? "-" : Math.round(x * 100) + "%");
  el.innerHTML = `
    <div class="tiles">
      ${[["ข้อความ", c.messages], ["ผู้เข้าร่วม", c.participants], ["บทสนทนา", c.conversations], ["ข้อความต่อบทสนทนา", c.avg_turns], ["แบบประเมิน", c.assessments], ["ให้คะแนน", c.ratings], ["บันทึกความรู้สึก", c.journals ?? 0]]
        .map(([l, n]) => `<div class="tile"><div class="n">${n}</div><div class="l">${l}</div></div>`).join("")}
    </div>
    <div class="grid2">
      <div class="card"><h2>ระดับวิกฤตที่ระบบจับได้</h2>${bars(s.crisis_level, true)}</div>
      <div class="card"><h2>หัวข้อ</h2>${bars(s.topic)}</div>
      <div class="card"><h2>ประเภทการตอบ (intent)</h2>${bars(s.intent)}</div>
      <div class="card"><h2>ผลแบบประเมิน 9Q</h2>${bars(s.severity)}</div>
      <div class="card"><h2>ความพึงพอใจ (0-10)</h2>${bars(s.rating)}</div>
      <div class="card"><h2>อารมณ์ในบันทึก (1 แย่มาก - 5 ดีมาก)</h2>${bars(Object.fromEntries(Object.entries(s.journal_mood || {}).map(([k, n]) => [`${k} ${MOOD_LABEL[k] || ""}`, n])))}</div>
      <div class="card"><h2>ช่วงอายุ (ข้อความ)</h2>${bars(s.age_band)}</div>
      <div class="card">
        <h2>การติดป้ายของผู้ตรวจ</h2>
        <p class="muted" style="margin-top:0">ผู้ตรวจ 1 ติดแล้ว ${L.rater1} ข้อความ · ผู้ตรวจ 2 ติดแล้ว ${L.rater2} · ติดครบทั้งสองคน ${L.both}</p>
        <p>ความเห็นตรงกันเรื่องวิกฤต (Cohen's kappa): <strong>${L.kappa_crisis ?? "ยังน้อยเกินไป"}</strong></p>
        <p style="margin-bottom:0">ระบบเทียบกับป้ายผู้ตรวจ 1 (n=${sv.n}): Precision <strong>${pct(sv.precision)}</strong> · Recall <strong>${pct(sv.recall)}</strong> · F1 <strong>${sv.f1 ?? "-"}</strong>
          <br><span class="muted">TP ${sv.tp} · FP ${sv.fp} · FN ${sv.fn} (ป้าย moderate/high = วิกฤต)</span></p>
      </div>
    </div>`;
}

// ---------------------------------------------------------------- messages
function filtered() {
  const f = A.filter, q = f.q.trim().toLowerCase(), r = A.rater;
  return A.data.research_chat.filter((m) =>
    (!q || (m.user_text || "").toLowerCase().includes(q) || (m.bot_text || "").toLowerCase().includes(q) || (m.participant || "").includes(q)) &&
    (!f.crisis || (f.crisis === "any" ? m.crisis_level !== "NONE" : m.crisis_level === f.crisis)) &&
    (!f.topic || (m.topic || "-") === f.topic) && (!f.intent || m.intent === f.intent) &&
    (!f.unlabeled || !m[`rater${r}_crisis`]));
}
function opts(key) { return [...new Set(A.data.research_chat.map((m) => m[key] || "-"))].sort(); }
function tabMessages(el) {
  const f = A.filter, rows = filtered(), r = A.rater, other = r === "1" ? "2" : "1";
  el.innerHTML = `
    <div class="filters">
      <label>ค้นหา<input id="f-q" value="${esc(f.q)}" placeholder="ข้อความ หรือรหัสผู้เข้าร่วม" /></label>
      <label>วิกฤต<select id="f-crisis"><option value="">ทั้งหมด</option><option value="any">เฉพาะที่วิกฤต</option><option value="HIGH">HIGH</option><option value="MODERATE">MODERATE</option><option value="NONE">NONE</option></select></label>
      <label>หัวข้อ<select id="f-topic"><option value="">ทั้งหมด</option>${opts("topic").map((t) => `<option>${esc(t)}</option>`).join("")}</select></label>
      <label>intent<select id="f-intent"><option value="">ทั้งหมด</option>${opts("intent").map((t) => `<option>${esc(t)}</option>`).join("")}</select></label>
      <label style="display:flex;gap:0.35rem;align-items:center"><input type="checkbox" id="f-unl" ${f.unlabeled ? "checked" : ""} /> ยังไม่ได้ติดป้าย (ผู้ตรวจ ${r})</label>
      <button class="small-btn ghost" id="csv" type="button">ดาวน์โหลด CSV (${rows.length})</button>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>เวลา</th><th>ผู้เข้าร่วม</th><th>ข้อความผู้ใช้</th><th>คำตอบบอท</th><th>ระบบจับได้</th><th>ป้ายผู้ตรวจ ${r}</th></tr></thead>
      <tbody>${rows.slice(0, 500).map((m) => `
        <tr class="${m.crisis_level && m.crisis_level !== "NONE" ? "is-crisis" : ""}">
          <td style="white-space:nowrap">${fmtTime(m.created_at)}<br><span class="muted">ข้อที่ ${m.turn_no ?? "-"}</span></td>
          <td><button class="small-btn ghost" data-conv="${esc(m.conversation)}" type="button" title="ดูทั้งบทสนทนา">${esc(m.participant)}</button></td>
          <td class="msg">${esc(m.user_text)}</td>
          <td class="msg bot">${esc(m.bot_text)}</td>
          <td><span class="pill ${m.crisis_level !== "NONE" ? "crisis" : ""}">${esc(m.crisis_level)}${m.crisis_source ? " · " + esc(m.crisis_source) : ""}</span>
              <span class="pill">${esc(m.intent)}</span><span class="pill">${esc(m.topic || "-")}</span>${m.dialogue_id ? `<span class="pill">คลัง: ${esc(m.dialogue_id)}</span>` : ""}</td>
          <td><div class="label-box" data-id="${m.id}">
              <select data-k="rater${r}_crisis"><option value="">ป้ายวิกฤต…</option>${Object.entries(CRISIS_TH).map(([k, l]) => `<option value="${k}" ${m[`rater${r}_crisis`] === k ? "selected" : ""}>${l}</option>`).join("")}</select>
              <input data-k="rater${r}_topic" placeholder="หัวข้อที่ถูก" value="${esc(m[`rater${r}_topic`] || "")}" />
              <button class="small-btn" data-save type="button">บันทึก</button>
              <span class="other">${m[`rater${other}_crisis`] ? `ผู้ตรวจ ${other}: ${esc(CRISIS_TH[m[`rater${other}_crisis`]] || m[`rater${other}_crisis`])}` : ""}</span>
          </div></td>
        </tr>`).join("") || `<tr><td colspan="6" class="muted">ไม่มีข้อความตามตัวกรองนี้</td></tr>`}</tbody>
    </table></div>
    ${rows.length > 500 ? `<p class="muted">แสดง 500 แถวแรกจาก ${rows.length} ใช้ตัวกรองหรือดาวน์โหลด CSV เพื่อดูทั้งหมด</p>` : ""}`;
  el.querySelector("#f-crisis").value = f.crisis; el.querySelector("#f-topic").value = f.topic; el.querySelector("#f-intent").value = f.intent;
  const bind = (id, key, ev = "change", get = (e) => e.target.value) => el.querySelector(id).addEventListener(ev, (e) => { f[key] = get(e); tabMessages(el); if (ev === "input") { const i = el.querySelector(id); i.focus(); i.setSelectionRange(i.value.length, i.value.length); } });
  bind("#f-q", "q", "input"); bind("#f-crisis", "crisis"); bind("#f-topic", "topic"); bind("#f-intent", "intent");
  bind("#f-unl", "unlabeled", "change", (e) => e.target.checked);
  el.querySelector("#csv").addEventListener("click", () => download("jaidee_messages.csv", rows));
  el.querySelectorAll("[data-conv]").forEach((b) => b.addEventListener("click", () => { A.conv = b.dataset.conv; A.tab = "conversations"; renderMain(); }));
  el.querySelectorAll("[data-save]").forEach((b) => b.addEventListener("click", async () => {
    const box = b.closest(".label-box"), body = {};
    box.querySelectorAll("[data-k]").forEach((x) => { body[x.dataset.k] = x.value; });
    b.disabled = true; b.textContent = "กำลังบันทึก…";
    try {
      const saved = await api("PATCH", `/chat/${box.dataset.id}`, body);
      const row = A.data.research_chat.find((m) => String(m.id) === String(box.dataset.id)); Object.assign(row, saved);
      b.textContent = "บันทึกแล้ว ✓";
    } catch (err) { b.textContent = "ไม่สำเร็จ"; alertBox(err.message); }
    setTimeout(() => { b.disabled = false; b.textContent = "บันทึก"; }, 1500);
  }));
}
function alertBox(msg) { const n = document.createElement("div"); n.className = "toast toast-show"; n.textContent = msg; document.body.appendChild(n); setTimeout(() => n.remove(), 3500); }

// ---------------------------------------------------------------- conversations
function tabConversations(el) {
  const groups = new Map();
  for (const m of A.data.research_chat) { if (!groups.has(m.conversation)) groups.set(m.conversation, []); groups.get(m.conversation).push(m); }
  const list = [...groups.entries()].map(([id, ms]) => ({ id, ms: ms.sort((a, b) => (a.turn_no || 0) - (b.turn_no || 0)), last: ms.reduce((t, m) => (m.created_at > t ? m.created_at : t), "") }))
    .sort((a, b) => (a.last < b.last ? 1 : -1));
  if (!A.conv && list.length) A.conv = list[0].id;
  const cur = list.find((c) => c.id === A.conv);
  el.innerHTML = list.length ? `
    <div class="conv-layout">
      <div class="conv-list">${list.slice(0, 300).map((c) => `
        <button type="button" class="conv-item ${c.id === A.conv ? "active" : ""}" data-id="${esc(c.id)}">
          <strong>${esc(c.ms[0].participant)}</strong> · ${c.ms.length} ข้อความ ${c.ms.some((m) => m.crisis_level !== "NONE") ? '<span class="pill crisis">วิกฤต</span>' : ""}<br>
          <span class="muted">${fmtTime(c.last)} · ${esc((c.ms[0].user_text || "").slice(0, 40))}</span></button>`).join("")}</div>
      <div class="card">${cur ? `<div class="transcript">${cur.ms.map((m) => `
          <div class="t-user">${esc(m.user_text)}</div>
          <div class="t-meta">${esc(m.intent)} · ${esc(m.topic || "-")} · วิกฤต ${esc(m.crisis_level)}</div>
          ${(m.bot_text || "").split("\n\n").map((b) => `<div class="t-bot">${esc(b)}</div>`).join("")}`).join("")}</div>` : ""}</div>
    </div>` : `<p class="muted">ยังไม่มีบทสนทนา</p>`;
  el.querySelectorAll(".conv-item").forEach((b) => b.addEventListener("click", () => { A.conv = b.dataset.id; tabConversations(el); }));
}

// ---------------------------------------------------------------- assessments / ratings
function simpleTable(el, rows, cols, name) {
  el.innerHTML = `
    <div class="filters"><button class="small-btn ghost" id="csv" type="button">ดาวน์โหลด CSV (${rows.length})</button></div>
    <div class="table-wrap"><table><thead><tr>${cols.map(([, l]) => `<th>${l}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${cols.map(([k, , f]) => `<td>${f ? f(r[k], r) : esc(r[k] ?? "-")}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${cols.length}" class="muted">ยังไม่มีข้อมูล</td></tr>`}</tbody></table></div>`;
  el.querySelector("#csv").addEventListener("click", () => download(name, rows));
}
function tabAssessments(el) {
  simpleTable(el, A.data.research_assessment, [
    ["created_at", "เวลา", fmtTime], ["participant", "ผู้เข้าร่วม"], ["total_score", "คะแนนรวม"], ["severity_level", "ระดับ"],
    ["q9_value", "ข้อ 9", (v) => (v > 0 ? `<span class="pill crisis">${v}</span>` : esc(v ?? "-"))],
    ["answers", "คำตอบรายข้อ", (v) => esc((v || []).map((a) => `${a.q}:${a.v}`).join(" "))], ["age_band", "อายุ"],
  ], "jaidee_assessments.csv");
}
function tabRatings(el) {
  simpleTable(el, A.data.research_rating, [["created_at", "เวลา", fmtTime], ["participant", "ผู้เข้าร่วม"], ["conversation", "บทสนทนา"], ["bucket", "คะแนน (0-10)"]], "jaidee_ratings.csv");
}

// v30 บันทึกความรู้สึก (ข้อความลบข้อมูลส่วนตัวแล้ว)
const MOOD_LABEL = { 1: "แย่มาก", 2: "ไม่ค่อยดี", 3: "เฉยๆ", 4: "ดี", 5: "ดีมาก" };
function tabJournal(el) {
  simpleTable(el, A.data.research_journal, [
    ["created_at", "เวลา", fmtTime], ["participant", "ผู้เข้าร่วม"], ["mood", "อารมณ์", (v) => esc(`${v} ${MOOD_LABEL[v] || ""}`)],
    ["crisis_level", "วิกฤต", (v) => (v && v !== "NONE" ? `<span class="pill crisis">${esc(v)}</span>` : esc(v ?? "-"))],
    ["text", "ข้อความ"], ["text_length", "ความยาว"], ["age_band", "อายุ"],
  ], "jaidee_journal.csv");
}

// ---------------------------------------------------------------- start
(async () => {
  if (!A.token) return renderLogin();
  try { await loadAll(); renderMain(); } catch (err) { renderLogin(err.message); }
})();
